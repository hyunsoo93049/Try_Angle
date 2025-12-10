# CLAUDE.md - TryAngle AI Development Guide

> **AI 어시스턴트를 위한 프로젝트 가이드**
>
> 이 문서는 Claude Code, GPT, 또는 다른 AI 어시스턴트가 TryAngle 프로젝트를 효과적으로 이해하고 개발에 참여할 수 있도록 작성되었습니다.

---

## 프로젝트 개요

**TryAngle**은 레퍼런스 이미지를 분석하여 실시간으로 촬영 가이드를 제공하는 AI 기반 사진 촬영 어시스턴트입니다.

- **버전**: 2.0.0 (Phase 1-3 통합 완료)
- **플랫폼**: iOS, Android (개발 중), Python Backend
- **핵심 기능**: 포즈 분석, 구도 가이드, 실시간 피드백

### 핵심 아이디어

1. 사용자가 레퍼런스 이미지(원하는 스타일의 사진)를 선택
2. 실시간 카메라로 피사체를 촬영
3. AI가 레퍼런스와 비교하여 실시간 피드백 제공

---

## 협업 환경

> **중요**: 이 저장소는 iOS와 Android 개발자가 함께 사용합니다.

### 플랫폼별 개발 영역

| 플랫폼 | 주요 디렉토리 | 언어 | 담당 역할 |
|--------|--------------|------|----------|
| **iOS** | `ios/`, `ios_v1.5/` | Swift/SwiftUI | 온디바이스 분석, UI |
| **Android** | (개발 예정) | Kotlin | 온디바이스 분석, UI |
| **Backend** | `backend/`, `src/Multi/version3/` | Python | FastAPI 서버, ML 분석 |

### iOS ↔ Android 협업

- `ios_v1.5/ANDROID_HANDOVER.md`: iOS 코드를 Android로 변환하기 위한 상세 가이드
- 공통 알고리즘 로직은 플랫폼 간 동일하게 유지
- ONNX 모델 파일은 양 플랫폼에서 공유 가능

---

## 프로젝트 구조

```
Try_Angle/
├── backend/                      # FastAPI 서버 (v2.0.0)
│   └── main.py                   # iOS/Android 연동 API
│
├── ios/                          # iOS 앱 (Swift, 기본 버전)
│   └── TryAngleApp/
│       ├── ContentView.swift     # 메인 UI
│       ├── Services/             # 분석/비교 서비스
│       │   ├── CameraManager.swift
│       │   ├── RealtimeAnalyzer.swift
│       │   └── Analysis/
│       └── Models/
│
├── ios_v1.5/                     # iOS 앱 (v1.5, 온디바이스 최적화)
│   └── TryAngleApp/
│       └── Services/
│           ├── OnDevice/         # 온디바이스 분석 핵심
│           │   ├── GateSystem.swift       # Gate 평가 로직
│           │   ├── MarginAnalyzer.swift   # 여백 분석
│           │   ├── GroundingDINOONNX.swift
│           │   └── UnifiedFeedbackGenerator.swift
│           ├── Analysis/         # 포즈/프레이밍 분석
│           │   └── RTMPoseRunner.swift
│           ├── Comparison/       # 비교 분석
│           └── RuleEngine/       # 규칙 기반 분석
│
├── src/Multi/version3/           # Python 메인 코드
│   ├── analysis/                 # 분석 모듈
│   │   ├── image_analyzer.py     # 통합 분석기
│   │   ├── image_comparator.py   # 비교 엔진
│   │   ├── pose_analyzer.py      # 포즈 분석 (YOLO11/MoveNet)
│   │   ├── exif_analyzer.py      # EXIF 추출
│   │   ├── quality_analyzer.py   # 품질 분석
│   │   └── lighting_analyzer.py  # 조명 분석
│   │
│   ├── utils/                    # Phase 1-3 유틸리티
│   │   ├── feedback_formatter.py # Top-K 필터링
│   │   ├── workflow_guide.py     # 5단계 워크플로우
│   │   ├── progress_tracker.py   # 진행도 추적
│   │   └── priority_system.py    # 우선순위 시스템
│   │
│   ├── camera_realtime.py        # 실시간 카메라 (PC)
│   └── main_feedback.py          # 통합 피드백 시스템
│
├── docs/                         # 개발자 문서
│   ├── 개발자인수인계.md
│   └── API가이드.md
│
├── data/                         # 데이터셋
│   ├── test_images/              # 테스트 이미지
│   └── contrastive_dataset/      # 대조학습 데이터
│
└── requirements.txt              # Python 의존성
```

---

## 개발 환경 설정

### Python 환경 (Backend/ML)

```bash
# 1. 환경 생성
conda create -n TA python=3.10 -y
conda activate TA

# 2. 의존성 설치
pip install -r requirements.txt

# 3. Git LFS로 모델 다운로드
git lfs pull
```

### iOS 개발 환경

```bash
# 1. CocoaPods 설치 (처음만)
sudo gem install cocoapods

# 2. Pod 설치
cd ios/
pod install

# 3. Xcode에서 .xcworkspace 열기
open TryAngleApp.xcworkspace
```

### iOS 최소 요구사항

- iOS 15.1+
- Xcode 14+
- CocoaPods
- ONNX Runtime (Podfile에 포함)

---

## 주요 명령어

### Python Backend 서버 실행

```bash
cd backend
python main.py
# 서버: http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

### Python 실시간 카메라 테스트

```bash
cd src/Multi/version3

# macOS/Linux
./run_camera.sh

# Windows
run_camera.bat

# 또는 직접 실행
python camera_realtime.py
```

### 통합 피드백 테스트

```bash
cd src/Multi/version3
python main_feedback.py
```

### iOS 빌드

```bash
cd ios
pod install
# Xcode에서 빌드 (Cmd+B)
```

---

## 핵심 API 엔드포인트

### FastAPI 서버 (backend/main.py)

| 엔드포인트 | 메소드 | 설명 |
|-----------|--------|------|
| `/` | GET | 서버 상태 확인 |
| `/api/analyze/realtime` | POST | 실시간 프레임 분석 |
| `/api/feedback/enhanced` | POST | Phase 1-3 통합 피드백 |
| `/api/progress/reset` | POST | 진행도 초기화 |
| `/api/recommendations` | GET | AI 레퍼런스 추천 |

### Python 코드 사용 예시

```python
# 이미지 분석
from analysis.image_analyzer import ImageAnalyzer

analyzer = ImageAnalyzer("image.jpg", enable_pose=True, enable_exif=True)
result = analyzer.analyze()

# 비교 & 피드백
from analysis.image_comparator import ImageComparator

comparator = ImageComparator("reference.jpg", "current.jpg")
feedback = comparator.get_prioritized_feedback()
```

---

## 아키텍처 핵심 개념

### 1. 상대적 평가 (Relative Evaluation)

레퍼런스 이미지의 스타일을 기준으로 비교합니다:

```python
# 레퍼런스가 흐린 스타일(blur=90)이면
# → 사용자가 더 흐려도 낮은 우선순위
# → "의도된 스타일"로 판단

if ref_blur < 100:  # 레퍼런스가 흐림 = 의도된 스타일
    priority = 8.0  # 낮은 우선순위
else:
    priority = 1.0  # 높은 우선순위
```

### 2. 피드백 우선순위 시스템

```
0.0  : CRITICAL (다시 찍기)
0.5  : 포즈
1.0  : 카메라 설정
2.0  : 거리
3.0  : 밝기
4.0  : 색감
5.0  : 구도/프레이밍
8.0  : 정보성 (스타일)
```

### 3. 워크플로우 5단계

```
1. 위치 설정 → 2. 구도 잡기 → 3. 포즈 조정 → 4. 카메라 설정 → 5. 품질 확인
```

### 4. Gate System (iOS v1.5)

iOS 온디바이스 분석에서 사용하는 4단계 평가:

| Gate | 항목 | Threshold |
|------|------|-----------|
| Gate 1 | 여백 균형 | 70% |
| Gate 2 | 프레이밍 | 65% |
| Gate 3 | 구도 | 70% |
| Gate 4 | 압축감 | 60% |

---

## 코드 컨벤션

### Python

- **들여쓰기**: 4 spaces
- **명명 규칙**: snake_case (함수, 변수), PascalCase (클래스)
- **타입 힌트**: 가능한 한 사용
- **Docstring**: Google 스타일

```python
def analyze_image(image_path: str, enable_pose: bool = True) -> dict:
    """
    이미지를 분석하여 특징을 추출합니다.

    Args:
        image_path: 이미지 파일 경로
        enable_pose: 포즈 분석 활성화 여부

    Returns:
        분석 결과 딕셔너리
    """
```

### Swift (iOS)

- **들여쓰기**: 4 spaces
- **명명 규칙**: camelCase (함수, 변수), PascalCase (타입)
- **접근 제어**: 가능한 한 private 사용
- **SwiftUI**: @State, @Published 적절히 사용

```swift
/// 이미지를 분석하여 피드백을 생성합니다.
/// - Parameters:
///   - image: 분석할 이미지
///   - referenceImage: 레퍼런스 이미지
/// - Returns: 피드백 배열
func analyzeImage(_ image: UIImage, reference: UIImage) -> [FeedbackItem]
```

---

## Git 워크플로우

### 브랜치 전략

```
main                 # 안정 버전
├── feature/*        # 새 기능 개발
├── fix/*            # 버그 수정
├── ios/*            # iOS 전용 개발
└── android/*        # Android 전용 개발
```

### 커밋 메시지 형식

```
feat: iOS 실시간 분석 기능 추가
fix: 포즈 검출 threshold 조정
docs: CLAUDE.md 업데이트
refactor: PersonDetector 리팩토링
perf: 실시간 분석 성능 최적화
```

### Git LFS 사용

대용량 파일은 Git LFS로 관리됩니다:

```bash
# LFS 파일 다운로드
git lfs pull

# LFS 추적 파일 확인
git lfs ls-files
```

---

## 주의사항

### 파일 크기 제한

`.gitignore`에서 제외되는 대용량 파일들:

- `*.pt`, `*.pth`, `*.onnx`, `*.tflite` (ML 모델)
- `*.npz`, `*.pkl`, `*.parquet` (특징 파일)
- `data/clustered_images/`, `features/`, `models/` (데이터 폴더)

### iOS/Android 좌표계 차이

- **iOS Vision**: Y축이 아래에서 위로 (0=하단, 1=상단)
- **Android**: 반대일 수 있음 - 변환 시 주의 필요

### 발열 관리

- iOS: `ThermalStateManager.swift`에서 처리
- Android: `PowerManager` 활용 권장
- 발열 상태에 따라 분석 간격 동적 조정

---

## 문서 참조

### 핵심 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| README.md | `/` | 프로젝트 전체 개요 |
| ANDROID_HANDOVER.md | `ios_v1.5/` | Android 변환 가이드 |
| 개발자인수인계.md | `docs/` | Phase 1-3 완료 내용 |
| API가이드.md | `docs/` | FastAPI 서버 사용법 |
| QUICK_REFERENCE.md | `src/Multi/version3/` | AI 어시스턴트 빠른 참조 |

### AI 어시스턴트 인수인계

`src/Multi/version3/QUICK_REFERENCE.md`의 "현재 작업 컨텍스트" 섹션을 확인하세요:

- 이전 AI가 작업한 내용
- 현재 상태 및 진행률
- 다음 작업 권장사항

작업 완료 후에는 해당 섹션을 업데이트하여 다음 AI 어시스턴트에게 인수인계하세요.

---

## 자주 발생하는 문제

### 1. ModuleNotFoundError

```bash
# 해결: TA 환경 활성화 확인
conda activate TA
pip install -r requirements.txt
```

### 2. Port 8000 already in use

```bash
# 다른 포트 사용
uvicorn main:app --host 0.0.0.0 --port 8001
```

### 3. ONNX Runtime 에러 (iOS)

```bash
# Pod 재설치
cd ios
pod deintegrate
pod install
```

### 4. Git LFS 파일 누락

```bash
git lfs install
git lfs pull
```

---

## 성능 참고

### Python 분석 속도

| 작업 | 첫 실행 | 캐시 후 |
|-----|---------|---------|
| 모델 로딩 | ~5초 | 0초 |
| 이미지 분석 | ~5초 | ~5초 |
| 실시간 FPS | - | 25-30 FPS |

### iOS 온디바이스 분석

| 발열 상태 | Level 1 | Level 2 | Level 3 |
|-----------|---------|---------|---------|
| nominal | 1프레임 | 5프레임 | 30프레임 |
| serious | 2프레임 | 10프레임 | 60프레임 |
| critical | 3프레임 | 15프레임 | 90프레임 |

---

## 연락 및 기여

### 팀 정보

- **소속**: 중앙대학교 예술공학부
- **기획**: 김현수
- **UX/UI 디자인**: 최승혜, 김세영, 이윤균
- **카메라 개발**: 전은서
- **알고리즘 및 AI개발**: 김현수

### 기여 방법

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

*이 문서는 2025-12-10에 생성되었습니다. 프로젝트 변경 시 업데이트가 필요합니다.*
