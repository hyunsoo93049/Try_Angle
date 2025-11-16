from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import os
import tempfile
import time

# TryAngle 코드 import
# 크로스 플랫폼 경로 지원
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, "src", "Multi", "version3"))
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
    서버에서는 포즈 피드백만 제공
    (프레이밍, 구도는 클라이언트에서 실시간 처리)
    """
    feedback = []

    # 포즈 피드백만 처리 (서버의 주요 역할)
    pose = comparison["pose_comparison"]
    if pose["available"]:
        # 포즈 피드백 안정화를 위해 더 엄격한 조건 적용
        if pose.get("similarity", 0) < 0.8:  # 80% 미만일 때만 피드백
            # 각도 차이 분석
            angle_diffs = pose.get("angle_differences", {})
            position_diffs = pose.get("position_differences", {})

            # 가장 큰 차이가 나는 부분 찾기
            major_issues = []

            for joint, diff in angle_diffs.items():
                if abs(diff) > 15:  # 15도 이상 차이날 때만
                    major_issues.append({
                        "joint": joint,
                        "diff": diff,
                        "type": "angle"
                    })

            # 상위 2개 문제만 피드백
            major_issues.sort(key=lambda x: abs(x["diff"]), reverse=True)

            for i, issue in enumerate(major_issues[:2]):
                if issue["type"] == "angle":
                    joint_name = translate_joint_name(issue["joint"])
                    direction = "더 올리세요" if issue["diff"] > 0 else "더 내리세요"

                    feedback.append({
                        "priority": i + 1,
                        "icon": "👤",
                        "message": f"{joint_name} {direction}",
                        "category": "pose",
                        "currentValue": 0,
                        "targetValue": abs(issue["diff"]),
                        "tolerance": 5,
                        "unit": "도"
                    })

        # 피드백이 있으면 원본 피드백도 추가 (텍스트만)
        elif pose["feedback"]:
            for i, fb in enumerate(pose["feedback"][:2]):
                if "적절합니다" not in fb:
                    feedback.append({
                        "priority": i + 3,
                        "icon": "💡",
                        "message": fb,
                        "category": "pose",
                        "currentValue": None,
                        "targetValue": None,
                        "tolerance": None,
                        "unit": None
                    })

    return feedback[:3]  # 포즈 피드백만 최대 3개


def translate_joint_name(joint: str) -> str:
    """영문 관절명을 한글로 번역"""
    translations = {
        "left_shoulder": "왼쪽 어깨",
        "right_shoulder": "오른쪽 어깨",
        "left_elbow": "왼쪽 팔꿈치",
        "right_elbow": "오른쪽 팔꿈치",
        "left_wrist": "왼쪽 손목",
        "right_wrist": "오른쪽 손목",
        "left_hip": "왼쪽 엉덩이",
        "right_hip": "오른쪽 엉덩이",
        "left_knee": "왼쪽 무릎",
        "right_knee": "오른쪽 무릎",
        "left_ankle": "왼쪽 발목",
        "right_ankle": "오른쪽 발목"
    }
    return translations.get(joint, joint)


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
