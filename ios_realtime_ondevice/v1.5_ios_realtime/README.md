# 📱 TryAngle iOS 실시간 버전

> iOS 디바이스에서 실시간으로 작동하는 사진 구도 피드백 시스템
>
> Version: 7.0 (iOS Realtime + On-Device)
>
> Last Updated: 2025-12-05

## 🎯 주요 특징

- **완전한 온디바이스 실행** - 네트워크 불필요
- **실시간 30fps 처리** - GPU 가속 활용
- **133 키포인트 포즈 검출** - RTMPose ONNX
- **깊이/압축감 분석** - Depth Anything CoreML

## 🚀 Quick Start

```python
from core.smart_feedback_v7 import SmartFeedbackV7

# 초기화
feedback_system = SmartFeedbackV7(mode='ios')

# 1. 레퍼런스 분석 (앱 시작시 1회)
reference_data = feedback_system.analyze_reference("reference.jpg")

# 2. 실시간 피드백 (카메라 프리뷰)
while camera.is_active():
    frame = camera.get_frame()
    feedback = feedback_system.process_frame(frame)
    display(feedback)
```

## 🎯 핵심 특징

### 1. 이중 모드 시스템
- **레퍼런스 모드**: 정확한 분석 (3-5초)
- **실시간 모드**: 빠른 피드백 (30fps)

### 2. 레퍼런스 기반 비교
- 프로 사진작가의 구도를 기준으로
- 실시간으로 차이점 분석 및 피드백

### 3. iOS 최적화
- CoreML 지원
- Metal Performance Shaders 활용
- 배터리 효율 고려

## 📊 성능

| 모드 | 처리 시간 | 정확도 | 용도 |
|------|-----------|--------|------|
| 레퍼런스 분석 | 3-5초 | 95% | 초기 1회 |
| 실시간 처리 | <33ms | 85% | 매 프레임 |

## 🏗️ 아키텍처

```
레퍼런스 분석 (1회)
    ↓
[캐싱 & 보정]
    ↓
실시간 처리 (30fps)
    ↓
피드백 생성
```

## 📱 iOS 통합

### Swift 브릿지 예제
```swift
class TryAngleCamera: UIViewController {
    let analyzer = SmartFeedbackBridge()

    override func viewDidLoad() {
        // 레퍼런스 설정
        analyzer.setReference(image: referenceImage)
    }

    func captureOutput(_ output: AVCaptureOutput,
                      didOutput sampleBuffer: CMSampleBuffer) {
        // 실시간 분석
        let feedback = analyzer.process(sampleBuffer)
        updateUI(feedback)
    }
}
```

## 🔧 설정

### 모델 설정
```yaml
# models/model_configs.yaml
reference_mode:
  grounding_dino: true
  depth_large: true
  rtmpose_133: true

realtime_mode:
  rtmpose_133: true
  depth_small: true
  yolo_nano: false  # 선택적
```

### 성능 튜닝
```python
# 프레임 스킵 설정
config = {
    'skip_frames': 2,      # 3프레임마다 처리
    'depth_interval': 5,   # 5프레임마다 depth
    'cache_timeout': 60    # 60초 캐시 유지
}
```

## 📁 프로젝트 구조

```
v1.5_ios_realtime/
├── core/           # 핵심 모듈
├── analyzers/      # 분석 엔진
├── realtime/       # 실시간 처리
├── models/         # AI 모델
└── tests/          # 테스트
```

## 🧪 테스트

```bash
# 실시간 성능 테스트
python tests/test_realtime.py

# 정확도 테스트
python tests/test_accuracy.py --reference sample_ref.jpg
```

## 📋 요구사항

### Python 패키지
```
opencv-python>=4.8.0
numpy>=1.24.0
torch>=2.0.0
pillow>=10.0.0
rtmlib>=0.0.9
transformers>=4.35.0
depth-anything>=0.1.0
```

### iOS 요구사항
- iOS 15.0+
- iPhone 12 이상 권장
- A14 Bionic 칩 이상

## 🔍 주요 컴포넌트

### SmartFeedbackV7
v6 기반 개선 버전. Gate System과 실시간 처리 통합

### CacheManager
레퍼런스 분석 결과를 캐싱하여 실시간 비교 성능 향상

### FrameProcessor
프레임별 처리 로직. Level 1/2/3 처리 관리

## 🐛 알려진 이슈

1. **첫 프레임 지연**
   - 모델 로딩으로 인한 1-2초 지연
   - 해결: 백그라운드 프리로딩

2. **메모리 사용량**
   - 피크시 350MB
   - 해결: 모델 양자화 적용

## 📈 개선 계획

- [ ] CoreML 변환 최적화
- [ ] Swift 네이티브 구현
- [ ] 실시간 학습 기능
- [ ] 클라우드 레퍼런스 라이브러리

## 💡 팁

1. **레퍼런스 선택**
   - 같은 장소/조명의 사진 권장
   - 프로 사진작가 작품 활용

2. **성능 최적화**
   - 밝은 곳에서 더 정확
   - 삼각대 사용시 안정적

## 📞 지원

- GitHub Issues: [링크]
- 이메일: tryangle@example.com

## 📄 라이선스

MIT License

---

**TryAngle** - 모두가 프로 사진작가처럼 📸