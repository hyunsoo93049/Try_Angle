from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import os
import tempfile
import time

# TryAngle 코드 import
sys.path.append(r"C:\try_angle\src\Multi\version3")
from analysis.image_comparator import ImageComparator

app = FastAPI(title="TryAngle iOS Backend")

# CORS 설정 (iOS에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """서버 상태 확인"""
    return {
        "message": "TryAngle iOS Backend",
        "version": "1.0.0",
        "status": "running ✅"
    }


@app.post("/api/analyze/realtime")
async def analyze_realtime(
    reference: UploadFile = File(...),
    current_frame: UploadFile = File(...)
):
    """
    실시간 프레임 분석

    iOS에서 레퍼런스 이미지와 현재 프레임을 전송하면
    AI 분석 후 피드백을 반환
    """
    start_time = time.time()

    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as ref_temp:
        ref_temp.write(await reference.read())
        ref_path = ref_temp.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as frame_temp:
        frame_temp.write(await current_frame.read())
        frame_path = frame_temp.name

    try:
        print(f"\n📸 분석 시작...")
        print(f"   레퍼런스: {ref_path}")
        print(f"   현재 프레임: {frame_path}")

        # TryAngle 분석 (기존 Python 코드 활용)
        comparator = ImageComparator(ref_path, frame_path)
        comparison = comparator.compare()

        # 사용자 피드백 추출 (행동 가능한 것만)
        user_feedback = extract_user_feedback(comparison)

        # 카메라 설정 추출 (자동 조정용)
        camera_settings = extract_camera_settings(comparison)

        elapsed = time.time() - start_time
        print(f"✅ 분석 완료! ({elapsed:.3f}초)")
        print(f"   피드백 {len(user_feedback)}개 생성")

        return JSONResponse({
            "userFeedback": user_feedback,
            "cameraSettings": camera_settings,
            "processingTime": f"{elapsed:.3f}s",
            "timestamp": time.time()
        })

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return JSONResponse({
            "error": str(e),
            "userFeedback": [],
            "cameraSettings": {}
        }, status_code=500)

    finally:
        # 임시 파일 삭제
        try:
            os.unlink(ref_path)
            os.unlink(frame_path)
        except:
            pass


def extract_user_feedback(comparison: dict) -> list:
    """
    사용자가 직접 행동할 수 있는 피드백만 추출
    (포즈, 거리, 구도, 프레이밍)
    """
    feedback = []

    # 1. 포즈 (최우선)
    pose = comparison["pose_comparison"]
    if pose["available"] and pose["feedback"]:
        for fb in pose["feedback"][:3]:  # 상위 3개만
            if fb != "✅ 포즈가 적절합니다":
                feedback.append({
                    "priority": 1,
                    "icon": "👤",
                    "message": fb,
                    "category": "pose"
                })

    # 2. 거리
    depth = comparison["depth_comparison"]
    if depth["action"] != "none":
        feedback.append({
            "priority": 2,
            "icon": "📏",
            "message": depth["feedback"],
            "category": "distance"
        })

    # 3. 구도
    comp = comparison["composition_comparison"]
    tilt_diff = comp["tilt_diff"]
    if abs(tilt_diff) > 3:
        direction = "왼쪽" if tilt_diff > 0 else "오른쪽"
        feedback.append({
            "priority": 3,
            "icon": "📐",
            "message": f"휴대폰을 {abs(tilt_diff):.0f}도 {direction}으로 기울이세요",
            "category": "composition"
        })

    # 4. 프레이밍 (줌)
    if pose["available"]:
        ref_bbox = comparison.get("pose_comparison", {}).get("bbox")
        user_bbox = comparison.get("pose_comparison", {}).get("bbox")
        # 줌 관련 피드백 추가 가능

    return feedback[:5]  # 최대 5개


def extract_camera_settings(comparison: dict) -> dict:
    """
    카메라에 자동 적용할 설정 값
    (ISO, 화이트밸런스, 노출 보정)
    """
    settings = {}

    # 1. ISO
    exif = comparison["exif_comparison"]
    if exif["available"]:
        ref_iso = exif["ref_settings"].get("iso")
        if ref_iso:
            settings["iso"] = int(ref_iso)

    # 2. 화이트밸런스 (Kelvin)
    color = comparison["color_comparison"]
    ref_temp = color["ref_temperature"]
    wb_map = {
        "cool": 6500,    # 차가운 톤
        "neutral": 5500, # 중성 톤
        "warm": 4500     # 따뜻한 톤
    }
    settings["wbKelvin"] = wb_map.get(ref_temp, 5500)

    # 3. 노출 보정 (EV)
    brightness = comparison["brightness_comparison"]
    settings["evCompensation"] = brightness["ev_adjustment"]

    return settings


if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("🚀 TryAngle iOS Backend Server Starting...")
    print("="*60)
    print("\n📱 iOS 앱에서 접속할 주소:")
    print("   http://YOUR_PC_IP:8000")
    print("\n💡 PC IP 확인 방법:")
    print("   Windows: ipconfig → 무선 LAN IPv4 주소")
    print("\n🔧 서버 중지: Ctrl + C")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
