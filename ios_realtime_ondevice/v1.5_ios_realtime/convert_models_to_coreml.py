"""
모델을 CoreML/ONNX로 변환하는 스크립트
작성일: 2025-12-05
"""

import os
import sys
import torch
import coremltools as ct
import numpy as np
from pathlib import Path

print("="*60)
print("TryAngle 모델 변환 스크립트")
print("="*60)

# ============================================================
# 1. Depth Anything → CoreML 변환
# ============================================================

def convert_depth_anything_to_coreml():
    """Depth Anything을 CoreML로 변환"""

    print("\n[1] Depth Anything → CoreML 변환")
    print("-"*40)

    try:
        # Depth Anything 모델 로드
        from transformers import pipeline

        print("1. Hugging Face에서 모델 다운로드 중...")
        depth_estimator = pipeline('depth-estimation', model='LiheYoung/depth-anything-small-hf')

        # PyTorch 모델 추출
        model = depth_estimator.model
        model.eval()

        print("2. 모델 트레이싱...")
        # 더미 입력 (518x518 - Depth Anything 기본 크기)
        dummy_input = torch.randn(1, 3, 518, 518)

        # 모델 트레이싱
        traced_model = torch.jit.trace(model, dummy_input)

        print("3. CoreML 변환 중...")

        # 방법 1: neuralnetwork 백엔드 (iOS 호환성 좋음)
        mlmodel = ct.convert(
            traced_model,
            inputs=[ct.ImageType(
                name="image",
                shape=dummy_input.shape,
                bias=[-0.485/0.229, -0.456/0.224, -0.406/0.225],
                scale=1.0/255.0/0.226
            )],
            convert_to='neuralnetwork'  # iOS 호환성
        )

        # 모델 저장
        output_path = "depth_anything_small.mlmodel"
        mlmodel.save(output_path)

        print(f"✅ CoreML 모델 저장 완료: {output_path}")
        print(f"   파일 크기: {os.path.getsize(output_path) / 1024 / 1024:.1f}MB")

        # 방법 2: mlprogram 백엔드 (최신, 더 효율적)
        print("\n4. mlprogram 버전도 변환 중...")
        mlmodel_program = ct.convert(
            traced_model,
            inputs=[ct.TensorType(
                name="input",
                shape=dummy_input.shape
            )],
            convert_to='mlprogram',
            minimum_deployment_target=ct.target.iOS16
        )

        output_path2 = "depth_anything_small.mlpackage"
        mlmodel_program.save(output_path2)
        print(f"✅ mlpackage 저장 완료: {output_path2}")

        return True

    except Exception as e:
        print(f"❌ Depth Anything 변환 실패: {e}")
        print("\n대안: Apple 공식 CoreML 모델 사용")
        print("다운로드: https://huggingface.co/apple/coreml-depth-anything-v2-small")
        return False


# ============================================================
# 2. RTMPose → ONNX 변환 (이미 구현됨)
# ============================================================

def check_rtmpose_onnx():
    """RTMPose ONNX 파일 확인"""

    print("\n[2] RTMPose ONNX 확인")
    print("-"*40)

    onnx_files = {
        "yolox_int8.onnx": "YOLOX 검출기 (24MB)",
        "rtmpose_int8.onnx": "RTMPose 133 키포인트 (55MB)"
    }

    ios_model_dir = Path("../../ios/TryAngleApp/Models")

    for filename, description in onnx_files.items():
        file_path = ios_model_dir / filename
        if file_path.exists():
            size_mb = file_path.stat().st_size / 1024 / 1024
            print(f"✅ {filename}: {description}")
            print(f"   경로: {file_path}")
            print(f"   크기: {size_mb:.1f}MB")
        else:
            print(f"❌ {filename} 없음")
            print(f"   예상 경로: {file_path}")

    print("\n참고: RTMPose ONNX 변환은 이미 구현되어 있습니다!")
    print("관련 코드: ios/TryAngleApp/Services/Analysis/RTMPoseRunner.swift")


# ============================================================
# 3. YOLO → CoreML 변환 (보너스)
# ============================================================

def convert_yolo_to_coreml():
    """YOLO v8을 CoreML로 변환"""

    print("\n[3] YOLO v8 → CoreML 변환")
    print("-"*40)

    try:
        from ultralytics import YOLO

        print("1. YOLOv8n 모델 로드 중...")
        model = YOLO('yolov8n.pt')

        print("2. CoreML 변환 중...")
        # CoreML로 export
        model.export(format='coreml', imgsz=640, nms=True)

        print("✅ YOLO CoreML 변환 완료")
        print("   출력: yolov8n.mlpackage")
        print("   iOS에서 바로 사용 가능!")

        return True

    except Exception as e:
        print(f"❌ YOLO 변환 실패: {e}")
        print("   pip install ultralytics 필요")
        return False


# ============================================================
# 4. 모델 크기 최적화
# ============================================================

def optimize_model_size():
    """모델 크기 최적화 팁"""

    print("\n[4] 모델 크기 최적화 방법")
    print("-"*40)

    print("""
1. 양자화 (Quantization)
   - INT8 양자화: 크기 75% 감소, 속도 3배 향상
   - Float16: 크기 50% 감소

2. 프루닝 (Pruning)
   - 불필요한 가중치 제거
   - 20-30% 크기 감소 가능

3. 지식 증류 (Knowledge Distillation)
   - 큰 모델 → 작은 모델로 학습
   - Depth Anything Large → Small

4. 모델 선택
   - Depth Anything: Small (24MB) vs Base (97MB)
   - RTMPose: Tiny vs Small vs Medium
   - YOLO: v8n (6MB) vs v8s (25MB)
""")


# ============================================================
# 5. 통합 iOS 프로젝트 구조
# ============================================================

def create_ios_project_structure():
    """iOS 프로젝트 구조 생성"""

    print("\n[5] iOS 프로젝트 구조")
    print("-"*40)

    structure = """
ios/
├── TryAngleApp/
│   ├── Models/                    # 모델 파일
│   │   ├── depth_anything_small.mlmodelc
│   │   ├── yolox_int8.onnx
│   │   └── rtmpose_int8.onnx
│   │
│   ├── Services/
│   │   ├── Analysis/
│   │   │   ├── RTMPoseRunner.swift      # ONNX Runtime
│   │   │   ├── DepthAnythingCoreML.swift # CoreML
│   │   │   └── PoseMLAnalyzer.swift     # 통합
│   │   │
│   │   └── Camera/
│   │       └── CameraService.swift
│   │
│   └── TryAngleApp-Bridging-Header.h    # ONNX Runtime C API
│
├── Podfile                         # onnxruntime-mobile-c
└── Info.plist                      # 카메라 권한
"""

    print(structure)
    print("\n모든 모델을 온디바이스에서 실행 가능!")


# ============================================================
# 메인 실행
# ============================================================

def main():
    """메인 함수"""

    # 1. Depth Anything 변환
    success = convert_depth_anything_to_coreml()

    # 2. RTMPose 확인
    check_rtmpose_onnx()

    # 3. YOLO 변환 (옵션)
    # convert_yolo_to_coreml()

    # 4. 최적화 팁
    optimize_model_size()

    # 5. 프로젝트 구조
    create_ios_project_structure()

    print("\n" + "="*60)
    print("변환 완료!")
    print("="*60)

    if success:
        print("\n✅ 온디바이스 실행 준비 완료:")
        print("   - RTMPose: ONNX Runtime (이미 구현)")
        print("   - Depth Anything: CoreML (변환 완료)")
        print("   - YOLO: 더미 모드 또는 CoreML")
        print("\n🚀 API 서버 없이 iOS에서 직접 실행 가능!")
    else:
        print("\n⚠️ 일부 변환 실패")
        print("   Apple 공식 모델 사용 권장")


if __name__ == "__main__":
    # 필요 패키지 확인
    required = ["torch", "coremltools", "transformers"]
    missing = []

    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"❌ 필요한 패키지 설치:")
        print(f"   pip install {' '.join(missing)}")
        print("\n특히 coremltools 설치:")
        print("   pip install coremltools")
        sys.exit(1)

    main()