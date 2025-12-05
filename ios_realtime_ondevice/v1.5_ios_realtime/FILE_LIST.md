# 📋 iOS 실시간 버전 필수 파일 목록
> 작성일: 2025-12-05
> 목적: v6 기반 iOS 실시간 버전에 필요한 파일 정리

## ✅ 기존 파일 (재사용)

### 핵심 분석 모듈
```
✓ compare_final_improved_v6.py     → core/smart_feedback_v7.py (수정 필요)
✓ improved_margin_analyzer.py      → analyzers/margin_analyzer.py (그대로)
✓ framing_analyzer.py             → analyzers/framing_analyzer.py (그대로)
✓ rtmpose_wholebody_analyzer.py   → analyzers/pose_analyzer.py (그대로)
```

### 설정 및 유틸
```
✓ feedback_config.py              → core/feedback_config.py (그대로)
```

### Legacy (선택적 사용)
```
△ legacy/reference_comparison.py  → models/reference_analyzer.py (레퍼런스용만)
```

## 🆕 새로 만들 파일

### 실시간 처리
```
□ realtime/frame_processor.py     # 프레임별 처리 로직
□ realtime/cache_manager.py       # 레퍼런스 캐싱 시스템
□ realtime/performance_monitor.py # 성능 모니터링
```

### 경량 모델 래퍼
```
□ models/depth_small_wrapper.py   # Depth Anything Small
□ models/yolo_nano_wrapper.py     # YOLO v8 Nano (선택)
□ models/model_loader.py          # 동적 모델 로딩
```

### 통합 모듈
```
□ core/smart_feedback_v7.py       # v6 개선 버전 (메인)
□ core/gate_system.py            # Gate System 분리
□ core/ios_adapter.py            # iOS 인터페이스
```

## 📁 최종 구조
```
v1.5_ios_realtime/
├── FINAL_ARCHITECTURE.md      # 전체 설계
├── FILE_LIST.md              # 이 문서
├── README.md                 # 사용 방법
│
├── core/
│   ├── smart_feedback_v7.py # 메인 클래스 (v6 기반)
│   ├── gate_system.py       # Gate System
│   ├── feedback_config.py   # 피드백 설정
│   └── ios_adapter.py       # iOS 브릿지
│
├── analyzers/
│   ├── margin_analyzer.py   # 여백 분석 (improved_margin_analyzer)
│   ├── framing_analyzer.py  # 프레이밍 분석
│   ├── pose_analyzer.py     # RTMPose 래퍼
│   └── depth_analyzer.py    # Depth 통합 래퍼
│
├── realtime/
│   ├── frame_processor.py   # 실시간 프레임 처리
│   ├── cache_manager.py     # 캐싱 관리
│   └── performance_monitor.py # 성능 추적
│
├── models/
│   ├── reference_analyzer.py # 레퍼런스 정밀 분석 (Legacy 활용)
│   ├── depth_small_wrapper.py # Depth Small
│   ├── yolo_nano_wrapper.py  # YOLO Nano
│   └── model_configs.yaml    # 모델 설정
│
└── tests/
    ├── test_realtime.py      # 실시간 테스트
    ├── test_accuracy.py      # 정확도 테스트
    └── test_images/          # 테스트 이미지
```

## 🔄 파일 복사 명령
```bash
# 1. 핵심 분석기 복사
cp compare_final_improved_v6.py v1.5_ios_realtime/core/smart_feedback_v7.py
cp improved_margin_analyzer.py v1.5_ios_realtime/analyzers/margin_analyzer.py
cp framing_analyzer.py v1.5_ios_realtime/analyzers/framing_analyzer.py
cp rtmpose_wholebody_analyzer.py v1.5_ios_realtime/analyzers/pose_analyzer.py

# 2. 설정 파일 복사
cp feedback_config.py v1.5_ios_realtime/core/feedback_config.py

# 3. Legacy (레퍼런스용)
cp legacy/reference_comparison.py v1.5_ios_realtime/models/reference_analyzer.py
```

## 📝 수정 필요 사항

### smart_feedback_v7.py (핵심 수정)
```python
# 기존 v6
self.legacy_comparator = ReferenceComparison()  # 항상 실행

# 수정 후
if mode == 'reference':
    self.reference_analyzer = ReferenceAnalyzer()  # 레퍼런스만
else:
    self.realtime_processor = RealtimeProcessor()  # 실시간용
```

### 새로운 처리 흐름
```python
# 1. 레퍼런스 분석 (1회)
reference_data = analyze_reference_once(ref_image)
cache_manager.save(reference_data)

# 2. 실시간 처리 (매 프레임)
cached_ref = cache_manager.get()
current_data = process_realtime(frame)
feedback = compare_and_generate(current_data, cached_ref)
```

## ⚠️ 주의사항

1. **v6 코드 최대한 재활용**
   - Gate System 로직 그대로
   - 피드백 생성 로직 그대로
   - Legacy 호출 부분만 조건부로

2. **모델 로딩 최적화**
   - Grounding DINO는 레퍼런스 모드에서만
   - 실시간은 RTMPose + Depth Small만

3. **성능 우선순위**
   - 정확도 < 반응속도
   - 30fps 유지가 최우선

## 🎯 다음 단계

1. [ ] 필요한 파일들 복사
2. [ ] smart_feedback_v7.py 수정
3. [ ] frame_processor.py 작성
4. [ ] cache_manager.py 작성
5. [ ] 통합 테스트