# 모델 설정 가이드

## 필요한 모델 파일

### 1. RTMPose ONNX 모델
- `yolox_int8.onnx` (24MB) - 인물 검출
- `rtmpose_int8.onnx` (55MB) - 133 키포인트 포즈

**다운로드 위치**: main 브랜치의 `ios/TryAngleApp/Models/` 폴더에서 복사

### 2. Depth Anything CoreML 모델

#### 옵션 A: Apple 공식 모델 (권장)
```bash
# Hugging Face에서 다운로드
https://huggingface.co/apple/coreml-depth-anything-v2-small

# 다운로드 후 이름 변경
DepthAnything_Small.mlmodelc
```

#### 옵션 B: 직접 변환
```bash
# Python 환경에서
pip install coremltools transformers torch
python ../convert_models_to_coreml.py
```

## Xcode 프로젝트 설정

### 1. 모델 파일 추가
1. Xcode에서 프로젝트 열기
2. `Models` 폴더 생성
3. 모델 파일들 드래그 앤 드롭
4. "Copy items if needed" 체크
5. Target membership 확인

### 2. Build Phases 설정
1. Target → Build Phases
2. Copy Bundle Resources 확인
3. 모델 파일들이 포함되어 있는지 확인

### 3. 파일 크기 확인
- 총 모델 크기: ~100MB
- 앱 크기 증가 예상: ~120MB (압축 후)

## 테스트

### 모델 로드 확인
```swift
// RTMPose
if let rtmpose = RTMPoseRunner() {
    print("✅ RTMPose 로드 성공")
}

// Depth Anything
let depth = DepthAnythingCoreML()
// 모델 파일이 없으면 에러 메시지 출력
```

## 트러블슈팅

### "모델 파일을 찾을 수 없습니다" 에러
1. Bundle Resources 확인
2. 파일 이름 및 확장자 확인
3. Build Clean 후 재빌드

### 메모리 부족
1. 모델을 순차적으로 로드
2. 사용하지 않는 모델 해제
3. 낮은 해상도로 테스트