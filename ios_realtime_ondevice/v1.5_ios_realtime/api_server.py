"""
FastAPI Server for iOS Bridge
작성일: 2025-12-05
iOS 앱과 Python 백엔드 연결
"""

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import cv2
import numpy as np
import io
from PIL import Image
import time
import uuid
from typing import Optional, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 프로젝트 모듈 임포트
from core.smart_feedback_v7 import SmartFeedbackV7
from realtime.frame_processor import FrameProcessor
from realtime.cache_manager import CacheManager
from realtime.async_processor import AsyncFrameProcessor

# FastAPI 앱 생성
app = FastAPI(title="TryAngle iOS API", version="1.5.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 시스템 인스턴스
feedback_system = None
cache_manager = None
frame_processor = None
async_processor = None
executor = ThreadPoolExecutor(max_workers=2)


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    global feedback_system, cache_manager, frame_processor, async_processor

    print("[API Server] 시스템 초기화 중...")

    # 시스템 초기화
    feedback_system = SmartFeedbackV7(mode='ios', language='ko')
    cache_manager = CacheManager()
    frame_processor = FrameProcessor(
        feedback_system=feedback_system,
        cache_manager=cache_manager,
        enable_depth=True,  # Depth 활성화
        enable_yolo=True    # YOLO 활성화
    )

    # 비동기 프로세서
    async_processor = AsyncFrameProcessor(frame_processor, max_workers=2)
    async_processor.start()

    # 워밍업
    print("[API Server] 모델 워밍업 중...")
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)

    # RTMPose 워밍업
    for _ in range(3):
        _ = feedback_system.wholebody.extract_wholebody_keypoints(dummy)

    # Depth 워밍업
    if frame_processor.depth_estimator:
        frame_processor.depth_estimator.warmup(dummy)

    # YOLO 워밍업
    if frame_processor.yolo_detector:
        frame_processor.yolo_detector.warmup(dummy)

    print("[API Server] 초기화 완료!")


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 정리"""
    if async_processor:
        async_processor.stop()
    executor.shutdown(wait=False)
    print("[API Server] 종료")


@app.get("/")
async def root():
    """상태 확인"""
    return {
        "status": "running",
        "version": "1.5.0",
        "models": {
            "rtmpose": "loaded",
            "depth": "loaded" if frame_processor and frame_processor.depth_estimator else "disabled",
            "yolo": "loaded" if frame_processor and frame_processor.yolo_detector else "disabled"
        }
    }


@app.post("/analyze_reference")
async def analyze_reference(image: UploadFile = File(...)):
    """
    레퍼런스 이미지 분석

    Args:
        image: 업로드된 이미지 파일

    Returns:
        분석 결과와 reference_id
    """
    try:
        # 이미지 읽기
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid image"}
            )

        # 레퍼런스 ID 생성
        ref_id = str(uuid.uuid4())[:8]

        # 레퍼런스 분석 (동기 처리)
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(
            executor,
            feedback_system.analyze_reference,
            img
        )

        # 캐시 저장
        if analysis and cache_manager:
            cache_manager.cache_reference(ref_id, analysis)

        return {
            "reference_id": ref_id,
            "analysis": analysis,
            "status": "success"
        }

    except Exception as e:
        print(f"[API Server] 레퍼런스 분석 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.post("/process_frame")
async def process_frame(
    image: UploadFile = File(...),
    ref_id: Optional[str] = Form(None)
):
    """
    실시간 프레임 처리

    Args:
        image: 업로드된 프레임 이미지
        ref_id: 레퍼런스 ID (선택)

    Returns:
        피드백 결과
    """
    try:
        # 이미지 읽기
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid image"}
            )

        # 비동기 처리 제출
        frame_id = async_processor.submit_frame(img, ref_id)

        # 결과 대기 (최대 100ms)
        result = None
        for _ in range(100):  # 100번 시도 (100ms)
            result = async_processor.get_result(timeout=0.001)
            if result:
                break
            await asyncio.sleep(0.001)

        if result and not result.skipped:
            # 정상 처리된 경우
            feedback_data = result.result.get('feedback', {})
            return {
                "frame_id": frame_id,
                "feedback": feedback_data,
                "processing_level": result.result.get('processing_level', 1),
                "depth_info": result.result.get('depth_info'),
                "processing_time_ms": result.processing_time * 1000,
                "status": "success"
            }
        else:
            # 스킵되거나 타임아웃
            return {
                "frame_id": frame_id,
                "feedback": {
                    "primary": "",
                    "suggestions": [],
                    "skipped": True
                },
                "status": "skipped"
            }

    except Exception as e:
        print(f"[API Server] 프레임 처리 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.post("/process_frame_sync")
async def process_frame_sync(
    image: UploadFile = File(...),
    ref_id: Optional[str] = Form(None)
):
    """
    동기식 프레임 처리 (테스트용)

    Args:
        image: 업로드된 프레임 이미지
        ref_id: 레퍼런스 ID (선택)

    Returns:
        피드백 결과
    """
    try:
        # 이미지 읽기
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid image"}
            )

        # 동기 처리
        start_time = time.perf_counter()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            frame_processor.process_frame,
            img,
            ref_id
        )
        processing_time = (time.perf_counter() - start_time) * 1000

        if result:
            return {
                "feedback": result.get('feedback', {}),
                "processing_level": result.get('processing_level', 1),
                "depth_info": result.get('depth_info'),
                "processing_time_ms": processing_time,
                "status": "success"
            }
        else:
            return {
                "feedback": {
                    "primary": "처리 실패",
                    "suggestions": []
                },
                "status": "error"
            }

    except Exception as e:
        print(f"[API Server] 동기 처리 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/stats")
async def get_stats():
    """성능 통계 조회"""
    stats = {
        "async_processor": {},
        "models": {}
    }

    # 비동기 프로세서 통계
    if async_processor:
        stats["async_processor"] = async_processor.get_stats()

    # 모델별 통계
    if feedback_system and hasattr(feedback_system.wholebody, 'get_stats'):
        stats["models"]["rtmpose"] = feedback_system.wholebody.get_stats()

    if frame_processor:
        if frame_processor.depth_estimator:
            stats["models"]["depth"] = frame_processor.depth_estimator.get_stats()
        if frame_processor.yolo_detector:
            stats["models"]["yolo"] = frame_processor.yolo_detector.get_stats()

    return stats


@app.post("/clear_cache")
async def clear_cache():
    """캐시 초기화"""
    if cache_manager:
        # 캐시 클리어 (메서드가 있다면)
        cache_manager.reference_cache.clear()
        cache_manager.calibration_factors.clear()

    if async_processor:
        async_processor.clear_queues()

    return {"status": "cache cleared"}


@app.post("/set_language")
async def set_language(language: str = Form("ko")):
    """언어 설정 변경"""
    if language not in ["ko", "en"]:
        return JSONResponse(
            status_code=400,
            content={"error": "Unsupported language"}
        )

    if feedback_system:
        from core.feedback_config import set_language
        set_language(language)
        feedback_system.language = language

    return {"status": "success", "language": language}


# 테스트용 HTML 페이지
@app.get("/test")
async def test_page():
    """테스트 페이지"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TryAngle iOS API Test</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }
            button { padding: 10px 20px; margin: 5px; }
            #result { background: #f0f0f0; padding: 10px; margin-top: 10px; }
            img { max-width: 300px; }
        </style>
    </head>
    <body>
        <h1>TryAngle iOS API Test</h1>

        <div class="section">
            <h2>1. Reference Analysis</h2>
            <input type="file" id="refImage" accept="image/*">
            <button onclick="analyzeReference()">Analyze Reference</button>
            <div id="refResult"></div>
        </div>

        <div class="section">
            <h2>2. Frame Processing</h2>
            <input type="file" id="frameImage" accept="image/*">
            <input type="text" id="refId" placeholder="Reference ID (optional)">
            <button onclick="processFrame()">Process Frame</button>
            <div id="frameResult"></div>
        </div>

        <div class="section">
            <h2>3. Statistics</h2>
            <button onclick="getStats()">Get Stats</button>
            <div id="statsResult"></div>
        </div>

        <script>
            async function analyzeReference() {
                const fileInput = document.getElementById('refImage');
                const file = fileInput.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('image', file);

                const response = await fetch('/analyze_reference', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                document.getElementById('refResult').innerHTML =
                    '<pre>' + JSON.stringify(result, null, 2) + '</pre>';

                if (result.reference_id) {
                    document.getElementById('refId').value = result.reference_id;
                }
            }

            async function processFrame() {
                const fileInput = document.getElementById('frameImage');
                const file = fileInput.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('image', file);

                const refId = document.getElementById('refId').value;
                if (refId) {
                    formData.append('ref_id', refId);
                }

                const response = await fetch('/process_frame', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                document.getElementById('frameResult').innerHTML =
                    '<pre>' + JSON.stringify(result, null, 2) + '</pre>';
            }

            async function getStats() {
                const response = await fetch('/stats');
                const result = await response.json();
                document.getElementById('statsResult').innerHTML =
                    '<pre>' + JSON.stringify(result, null, 2) + '</pre>';
            }
        </script>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    # 서버 실행
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )