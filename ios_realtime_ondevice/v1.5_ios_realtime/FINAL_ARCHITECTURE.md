# 📱 TryAngle iOS 실시간 버전 - 최종 아키텍처
> 작성일: 2025-12-05
> 버전: v7.0 (iOS Realtime)
> 기반: v6 + 실시간 최적화

## 🎯 핵심 요구사항

### 성능 목표
- **FPS**: 30fps 유지 (33ms/frame)
- **지연시간**: < 100ms (사용자 체감)
- **정확도**: 레퍼런스 대비 90% 이상
- **메모리**: < 300MB

### 기능 요구사항
1. **레퍼런스 기반 비교** (핵심!)
2. **실시간 피드백** (30fps)
3. **여백/구도 정확도**
4. **압축감(깊이) 분석**

---

## 🏗️ 시스템 아키텍처

### 1. 이중 모드 구조
```
┌─────────────────────────────────────────┐
│          Reference Analysis Mode         │
│  (레퍼런스 분석 - 1회, 정확도 우선)      │
│  - Grounding DINO: 정확한 bbox          │
│  - Depth Anything Large: 깊이 분석       │
│  - RTMPose 133: 상세 키포인트            │
│  시간: 3-5초 (한 번만)                   │
└─────────────────────────────────────────┘
                    ↓
            [캐싱 및 보정 계수 계산]
                    ↓
┌─────────────────────────────────────────┐
│          Realtime Camera Mode           │
│  (실시간 촬영 - 30fps, 속도 우선)        │
│  - RTMPose 133: 매 프레임               │
│  - Depth Anything Small: 3프레임마다     │
│  - YOLO Nano: 선택적 (1초마다)          │
│  시간: < 33ms/frame                     │
└─────────────────────────────────────────┘
```

### 2. 처리 레벨 시스템
```python
Level 1 (매 프레임 - 33ms 주기):
  - RTMPose 키포인트 추출
  - 빠른 여백 계산
  - 기본 가이드라인 표시

Level 2 (3프레임마다 - 100ms 주기):
  - Depth Anything Small
  - 압축감 분석
  - 상세 피드백 업데이트

Level 3 (30프레임마다 - 1초 주기):
  - YOLO Nano bbox 보정 (선택)
  - 누적 데이터 분석
  - 피드백 우선순위 조정
```

---

## 📁 파일 구조

```
v1.5_ios_realtime/
│
├── FINAL_ARCHITECTURE.md        # 이 문서 (전체 설계)
│
├── core/                        # 핵심 모듈
│   ├── smart_feedback_v7.py    # v6 기반 개선 버전
│   ├── gate_system.py          # Gate System (v6에서 분리)
│   └── feedback_generator.py   # 피드백 생성 로직
│
├── analyzers/                   # 분석 모듈
│   ├── margin_analyzer.py      # 개선된 여백 분석 (v6)
│   ├── framing_analyzer.py     # 프레이밍 분석 (v6)
│   ├── pose_analyzer.py        # RTMPose 래퍼
│   └── depth_analyzer.py       # Depth Anything 래퍼
│
├── realtime/                    # 실시간 처리
│   ├── frame_processor.py      # 프레임별 처리 로직
│   ├── cache_manager.py        # 레퍼런스 캐싱
│   └── performance_monitor.py  # 성능 모니터링
│
├── models/                      # 모델 관리
│   ├── model_loader.py         # 동적 모델 로딩
│   └── model_configs.yaml      # 모델 설정
│
└── tests/                       # 테스트
    ├── test_realtime.py        # 실시간 성능 테스트
    └── test_accuracy.py        # 정확도 테스트
```

---

## 🔧 핵심 컴포넌트

### 1. SmartFeedbackV7 (메인 클래스)
```python
class SmartFeedbackV7:
    """v6 기반 iOS 최적화 버전"""

    def __init__(self, mode='ios'):
        # v6 컴포넌트 재사용
        self.gate_system = GateSystem()  # v6
        self.margin_analyzer = ImprovedMarginAnalyzer()  # v6
        self.framing_analyzer = FramingAnalyzer()  # v6

        # 새로운 컴포넌트
        self.reference_analyzer = ReferenceAnalyzer()  # 정밀 분석
        self.realtime_processor = RealtimeProcessor()  # 실시간 처리
        self.cache_manager = CacheManager()  # 캐싱

    def analyze_reference(self, ref_image):
        """레퍼런스 정밀 분석 (1회)"""
        # Grounding DINO + Depth Large + RTMPose
        # 결과 캐싱

    def process_frame(self, frame):
        """실시간 프레임 처리 (30fps)"""
        # RTMPose + Depth Small
        # 캐시된 레퍼런스와 비교
```

### 2. 모델 전략

| 단계 | 모델 | 용도 | 처리시간 |
|------|------|------|----------|
| **레퍼런스** | Grounding DINO | 정확한 bbox | 300ms |
| | Depth Anything Large | 정확한 깊이 | 200ms |
| | RTMPose 133 | 전체 키포인트 | 60ms |
| **실시간** | RTMPose 133 | 키포인트 | 40ms |
| | Depth Anything Small | 깊이 추정 | 30ms |
| | YOLO Nano (선택) | bbox 보정 | 10ms |

### 3. 캐싱 전략
```python
class CacheManager:
    def __init__(self):
        self.reference_cache = {}  # 레퍼런스 분석 결과
        self.calibration = {}      # 보정 계수

    def cache_reference(self, ref_id, analysis):
        """레퍼런스 분석 결과 저장"""
        self.reference_cache[ref_id] = {
            'grounding_dino_bbox': analysis['bbox'],
            'depth_map': analysis['depth'],
            'keypoints': analysis['keypoints'],
            'margins': analysis['margins'],
            'compression': analysis['compression']
        }

    def get_calibration_factor(self, ref_id):
        """RTMPose vs Grounding DINO 보정 계수"""
        return self.calibration.get(ref_id, 1.0)
```

---

## 💡 핵심 인사이트

### 1. 여백 계산 일관성
```python
# 문제: 레퍼런스는 Grounding DINO, 실시간은 RTMPose
# 해결: 보정 계수 적용

calibration_factor = grounding_dino_bbox / rtmpose_bbox
realtime_margin = rtmpose_margin * calibration_factor
```

### 2. Gate System 우선순위
```python
GATE_PRIORITY = [
    'aspect_ratio',  # 1순위: 종횡비 (필수)
    'framing',       # 2순위: 프레이밍
    'composition',   # 3순위: 구도
    'compression'    # 4순위: 압축감
]
```

### 3. 피드백 전략
```python
# 실시간: 간단한 가이드
"← 왼쪽으로"

# 주기적: 구체적 지시
"인물을 10% 왼쪽으로 이동"

# 상세: 전체 분석
"레퍼런스 대비:
 - 좌우 균형 15% 차이
 - 상단 여백 부족
 - 압축감 과도"
```

---

## 🚀 구현 로드맵

### Phase 1: 기본 구조 (1일)
- [ ] 폴더 구조 생성
- [ ] v6 코드 분리 및 정리
- [ ] 기본 클래스 구조

### Phase 2: 레퍼런스 분석 (2일)
- [ ] Grounding DINO 통합
- [ ] Depth Anything Large 통합
- [ ] 캐싱 시스템

### Phase 3: 실시간 처리 (3일)
- [ ] RTMPose 최적화
- [ ] Depth Small 통합
- [ ] 프레임 처리 파이프라인

### Phase 4: 통합 및 최적화 (2일)
- [ ] 전체 통합
- [ ] 성능 최적화
- [ ] iOS 테스트

---

## 📊 성능 목표 vs 현실

| 항목 | 목표 | 현재 예상 | 달성 방법 |
|------|------|-----------|-----------|
| FPS | 30 | 25-30 | 프레임 스킵 |
| 레퍼런스 분석 | < 5초 | 3-5초 | 병렬 처리 |
| 실시간 지연 | < 100ms | 80-120ms | 캐싱 활용 |
| 메모리 | < 300MB | 250-350MB | 모델 양자화 |

---

## ⚠️ 주의사항

1. **Legacy 시스템 의존 제거**
   - v6의 legacy_comparator 직접 호출 금지
   - 필요시 선택적 사용

2. **일관된 비교 기준**
   - 레퍼런스와 현재 모두 같은 방식 측정
   - 또는 보정 계수 적용

3. **실시간 우선순위**
   - 정확도보다 반응성
   - 피드백은 방향성 중심

---

## 📝 참고 코드

### v6에서 가져올 핵심 부분
```python
# 1. Gate System
from compare_final_improved_v6 import (
    _check_aspect_ratio,
    _check_framing_debug,
    _check_composition,
    _check_compression_debug
)

# 2. 여백 분석
from improved_margin_analyzer import ImprovedMarginAnalyzer

# 3. 프레이밍
from framing_analyzer import FramingAnalyzer

# 4. 피드백 생성 로직
# (전체 구조는 유지, Legacy 호출만 수정)
```

---

## 🎯 성공 지표

1. **기술적 지표**
   - [ ] 30fps 실시간 처리
   - [ ] 레퍼런스 분석 < 5초
   - [ ] 메모리 사용 < 300MB

2. **사용자 경험**
   - [ ] 즉각적인 피드백
   - [ ] 정확한 구도 가이드
   - [ ] 일관된 비교 결과

3. **코드 품질**
   - [ ] v6 코드 80% 재사용
   - [ ] 모듈화된 구조
   - [ ] 테스트 커버리지 > 70%

---

**이 문서를 참고하여 구현을 진행하세요!**