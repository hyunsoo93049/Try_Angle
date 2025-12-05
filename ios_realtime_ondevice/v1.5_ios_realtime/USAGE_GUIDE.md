# TryAngle iOS v1.5 사용 가이드

## 실행 방식 선택

### 방식 1: 완전한 온디바이스 (권장) 📱

**장점**
- 네트워크 불필요
- 빠른 응답 (30fps)
- 프라이버시 보장

**사용 파일**
```
ios_bridge/
├── TryAngleOnDevice.swift      # 메인 통합 시스템
├── RTMPoseRunner.swift         # ONNX 포즈 검출
├── DepthAnythingCoreML.swift   # CoreML 깊이 추정
└── MODEL_SETUP_GUIDE.md        # 모델 설정
```

**실행 방법**
```swift
// ViewController에서
let analyzer = TryAngleOnDeviceAnalyzer()
analyzer.analyzeFrame(image) { feedback in
    // UI 업데이트
}
```

---

### 방식 2: API 서버 연동 🌐

**장점**
- 작은 앱 크기
- 모델 업데이트 쉬움
- Python 모델 그대로 사용

**사용 파일**
```
# 서버 (Python)
api_server.py
models/
core/
realtime/

# 클라이언트 (Swift)
ios_bridge/TryAngleBridge.swift
```

**실행 방법**

1. 서버 시작
```bash
cd v1.5_ios_realtime
python api_server.py
```

2. iOS 앱에서
```swift
let bridge = TryAngleBridge(serverURL: "http://localhost:8000")
bridge.processFrame(pixelBuffer)
```

---

## 어떤 방식을 선택할까?

### 온디바이스를 선택하세요 if:
- ✅ 오프라인 동작 필요
- ✅ 최대 성능 필요
- ✅ 프라이버시 중요
- ✅ 앱 크기 100MB 증가 괜찮음

### API 서버를 선택하세요 if:
- ✅ 앱 크기 최소화 필요
- ✅ 자주 모델 업데이트
- ✅ 서버 운영 가능
- ✅ 네트워크 항상 가능

---

## 하이브리드 방식 (고급)

두 방식을 모두 구현하고 상황에 따라 전환:

```swift
class TryAngleAnalyzer {
    private var onDevice: TryAngleOnDeviceAnalyzer?
    private var apiClient: TryAngleBridge?

    init(mode: AnalysisMode) {
        switch mode {
        case .onDevice:
            self.onDevice = TryAngleOnDeviceAnalyzer()
        case .api:
            self.apiClient = TryAngleBridge()
        case .hybrid:
            // 네트워크 상태에 따라 자동 전환
            self.onDevice = TryAngleOnDeviceAnalyzer()
            self.apiClient = TryAngleBridge()
        }
    }
}
```

---

## 성능 비교

| 항목 | 온디바이스 | API 서버 |
|-----|-----------|----------|
| 응답속도 | 30ms | 50-100ms |
| FPS | 30 | 10-15 |
| 앱 크기 | +100MB | +5MB |
| 네트워크 | 불필요 | 필수 |
| 정확도 | 동일 | 동일 |

---

## 문제 해결

### Q: 모델이 로드되지 않아요
A: MODEL_SETUP_GUIDE.md 참조

### Q: 30fps가 안나와요
A: 프레임 스킵 레벨 조정
```swift
private let processEveryNFrames = 2  // 2로 줄이기
```

### Q: 메모리 부족
A: 한 번에 하나의 모델만 사용
```swift
// Depth 비활성화
let analyzer = TryAngleOnDeviceAnalyzer(enableDepth: false)
```