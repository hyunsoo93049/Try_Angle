# 📱 안드로이드 포팅에 필요한 전체 파일 목록

## ✅ 필수 파일 (6개)

### 1. 핵심 알고리즘 파일 (5개)

| 파일명 | 경로 | 역할 | 우선순위 |
|--------|------|------|----------|
| **RTMPoseRunner.swift** | `Services/Analysis/` | ONNX 모델 추론 | ⭐⭐⭐ 최우선 |
| **PhotographyFramingAnalyzer.swift** | `Services/Analysis/` | 프레이밍 분석 | ⭐⭐⭐ 최우선 |
| **AdaptivePoseComparator.swift** | `Services/Comparison/` | 포즈 비교 | ⭐⭐⭐ 최우선 |
| **StagedFeedbackGenerator.swift** | `Services/Comparison/` | 피드백 생성 | ⭐⭐⭐ 최우선 |
| **RealtimeAnalyzer.swift** | `Services/` | 파이프라인 통합 | ⭐⭐ 중요 |

### 2. 데이터 모델 파일 (1개) ⚠️ 빠뜨렸던 필수 파일!

| 파일명 | 경로 | 역할 | 우선순위 |
|--------|------|------|----------|
| **Feedback.swift** | `Models/` | 모든 데이터 구조 정의 | ⭐⭐⭐ 최우선 |

---

## 📦 Feedback.swift에 정의된 필수 데이터 구조

**위치:** `ios/TryAngleApp/Models/Feedback.swift`

### 필수 구조체/Enum (Android에서 재정의 필요):

```swift
// 1. 포즈 키포인트 (RTMPoseRunner 출력)
struct PoseKeypoint {
    let location: CGPoint  // (x, y) 좌표
    let confidence: Float  // 0.0 ~ 1.0
}
```

```swift
// 2. 카메라 비율 (전체 시스템에서 사용)
enum CameraAspectRatio: String {
    case ratio16_9 = "16:9"
    case ratio4_3 = "4:3"
    case ratio1_1 = "1:1"

    var ratio: CGFloat { ... }
    static func detect(from size: CGSize) -> CameraAspectRatio
}
```

```swift
// 3. 피드백 카테고리 (우선순위 시스템)
enum FeedbackCategory: String {
    case pose           // 1순위
    case position       // 2순위
    case framing        // 3순위
    case angle          // 4순위
    case composition    // 5순위
    case gaze           // 6순위

    var priority: Int { ... }
    var displayName: String { ... }
    var icon: String { ... }
}
```

```swift
// 4. 피드백 아이템 (최종 출력)
struct FeedbackItem: Codable {
    let priority: Int
    let icon: String        // "📸", "🤸" 등
    let message: String     // "카메라를 위로 올려주세요"
    let category: String    // "framing", "pose" 등

    // 진행도 추적 (옵션)
    let currentValue: Double?
    let targetValue: Double?
    let tolerance: Double?
    let unit: String?
}
```

```swift
// 5. 카테고리별 상태 (UI 체크 표시용)
struct CategoryStatus {
    let category: FeedbackCategory
    let isSatisfied: Bool
    let activeFeedbacks: [FeedbackItem]
}
```

```swift
// 6. 완료된 피드백 (애니메이션용, 옵션)
struct CompletedFeedback {
    let item: FeedbackItem
    let completedAt: Date
}
```

---

## 📦 PhotographyFramingAnalyzer.swift 내부 구조

**이 파일 안에 다음 구조들이 함께 정의되어 있음:**

```swift
// 샷 타입 (필수!)
enum ShotType: String {
    case extremeCloseUp     // 얼굴만
    case closeUp            // 머리~어깨
    case mediumCloseUp      // 머리~가슴
    case mediumShot         // 머리~허리
    case americanShot       // 머리~무릎
    case fullShot           // 전신
}
```

```swift
// 프레이밍 분석 결과 (필수!)
struct PhotographyFramingResult {
    let shotType: ShotType
    let padding: ImagePadding           // 상하좌우 여백
    let croppedParts: [KeypointGroup]   // 잘린 부위들
    let nosePosition: CGPoint           // 코 위치
    let bodyBoundingBox: CGRect         // 전신 영역
}
```

```swift
// 키포인트 그룹 (필수!)
enum KeypointGroup: String {
    case head       // 머리
    case hands      // 손
    case feet       // 발
    case legs       // 다리
    case arms       // 팔
}
```

---

## 📦 AdaptivePoseComparator.swift 내부 구조

```swift
// 포즈 타입 (필수!)
enum PoseType {
    case standing   // 서 있는 자세
    case sitting    // 앉은 자세
    case custom     // 기타
}
```

```swift
// 키포인트 그룹 (크롭 감지용, 필수!)
enum KeypointGroup: String {
    case head, face, shoulders, arms, hands
    case torso, hips, legs, feet
}
```

```swift
// 포즈 비교 결과 (필수!)
struct PoseComparisonResult {
    let angleDifferences: [String: Float]       // "left_elbow": 15.0 (도)
    let angleDirections: [String: String]       // "left_elbow": "팔을 더 펴세요"
    let positionDifferences: [String: CGPoint]  // 위치 차이
    let overallSimilarity: Float                // 0.0 ~ 1.0
    let misalignedParts: [String]               // 어긋난 부위들
}
```

---

## 📦 RealtimeAnalyzer.swift 내부 구조

```swift
// 프레임 분석 결과 (파이프라인 내부용, 옵션)
struct FrameAnalysis {
    let faceRect: CGRect?
    let bodyRect: CGRect?
    let brightness: Float
    let tiltAngle: Float
    let faceYaw: Float?
    let facePitch: Float?
    let cameraAngle: CameraAngle
    let poseKeypoints: [(point: CGPoint, confidence: Float)]?
    let compositionType: CompositionType?
    let faceObservation: VNFaceObservation?
    let gaze: GazeResult?
    let depth: DepthResult?
    let aspectRatio: CameraAspectRatio
    let imagePadding: ImagePadding?
}
```

```swift
// 이미지 여백 정보 (필수!)
struct ImagePadding {
    let top: CGFloat        // 0.0 ~ 1.0
    let bottom: CGFloat
    let left: CGFloat
    let right: CGFloat

    var hasExcessivePadding: Bool { ... }
}
```

---

## 🎯 Android 구현 가이드라인

### 단계 1: 데이터 클래스 먼저 정의

**순서대로 구현:**

1. **Feedback.kt** (Feedback.swift 변환)
   ```kotlin
   data class PoseKeypoint(val x: Float, val y: Float, val confidence: Float)

   enum class CameraAspectRatio(val ratio: Float) {
       RATIO_16_9(16f / 9f),
       RATIO_4_3(4f / 3f),
       RATIO_1_1(1f)
   }

   enum class FeedbackCategory(val priority: Int, val icon: String) {
       POSE(1, "🤸"),
       POSITION(2, "📍"),
       FRAMING(3, "📸"),
       ANGLE(4, "📷"),
       COMPOSITION(5, "🎨"),
       GAZE(6, "👀")
   }

   data class FeedbackItem(
       val priority: Int,
       val icon: String,
       val message: String,
       val category: String
   )
   ```

2. **ShotType.kt** (PhotographyFramingAnalyzer.swift에서 추출)
   ```kotlin
   enum class ShotType {
       EXTREME_CLOSE_UP,
       CLOSE_UP,
       MEDIUM_CLOSE_UP,
       MEDIUM_SHOT,
       AMERICAN_SHOT,
       FULL_SHOT
   }
   ```

3. **PhotographyFramingResult.kt**
   ```kotlin
   data class ImagePadding(
       val top: Float,
       val bottom: Float,
       val left: Float,
       val right: Float
   )

   data class PhotographyFramingResult(
       val shotType: ShotType,
       val padding: ImagePadding,
       val croppedParts: List<KeypointGroup>,
       val nosePosition: PointF,
       val bodyBoundingBox: RectF
   )
   ```

4. **PoseComparisonResult.kt**
   ```kotlin
   data class PoseComparisonResult(
       val angleDifferences: Map<String, Float>,
       val angleDirections: Map<String, String>,
       val positionDifferences: Map<String, PointF>,
       val overallSimilarity: Float,
       val misalignedParts: List<String>
   )
   ```

### 단계 2: 알고리즘 구현

데이터 클래스를 먼저 정의한 후, 5개 핵심 알고리즘 파일을 순서대로 변환:

1. RTMPoseRunner.kt
2. PhotographyFramingAnalyzer.kt
3. AdaptivePoseComparator.kt
4. StagedFeedbackGenerator.kt
5. RealtimeAnalyzer.kt

---

## 📋 전체 파일 체크리스트

### ✅ 필수 파일

- [ ] `Feedback.swift` → `Feedback.kt` (모든 데이터 구조)
- [ ] `RTMPoseRunner.swift` → `RTMPoseRunner.kt`
- [ ] `PhotographyFramingAnalyzer.swift` → `PhotographyFramingAnalyzer.kt`
- [ ] `AdaptivePoseComparator.swift` → `AdaptivePoseComparator.kt`
- [ ] `StagedFeedbackGenerator.swift` → `StagedFeedbackGenerator.kt`
- [ ] `RealtimeAnalyzer.swift` → `RealtimeAnalyzer.kt`

### ✅ 모델 파일

- [ ] `rtmpose_int8.onnx` (218MB)
- [ ] `yolox_int8.onnx` (97MB, 옵션)

### ✅ 문서

- [ ] `ANDROID_PORTING_GUIDE.md`
- [ ] `ONNX_MODELS_INFO.md`

---

## ⚠️ 주의사항

### 빠뜨리면 안 되는 것들:

1. **Feedback.swift는 필수!**
   - 모든 파일이 이 안의 데이터 구조를 사용합니다
   - 없으면 컴파일 자체가 안 됩니다

2. **각 파일 내부의 enum/struct도 함께 포팅**
   - `ShotType` (PhotographyFramingAnalyzer.swift 안에 있음)
   - `PoseComparisonResult` (AdaptivePoseComparator.swift 안에 있음)
   - 이것들을 별도 파일로 분리하거나 같은 파일 안에 포함

3. **타입 변환 주의**
   - Swift `CGPoint` → Kotlin `PointF`
   - Swift `CGRect` → Kotlin `RectF`
   - Swift `CGFloat` → Kotlin `Float`
   - Swift `[String: Float]` → Kotlin `Map<String, Float>`

---

## 🚀 빠른 시작 가이드

### 안드로이드 개발자가 할 일:

```bash
# 1. 브랜치 클론
git clone https://github.com/hyunsoo93049/Try_Angle.git
git checkout android-port-reference

# 2. 파일 위치 확인
cd ios/TryAngleApp
ls Models/Feedback.swift
ls Services/Analysis/RTMPoseRunner.swift
ls Services/Analysis/PhotographyFramingAnalyzer.swift
ls Services/Comparison/AdaptivePoseComparator.swift
ls Services/Comparison/StagedFeedbackGenerator.swift
ls Services/RealtimeAnalyzer.swift

# 3. 모델 파일 복사
cp Models/ONNX/rtmpose_int8.onnx /path/to/android/app/src/main/assets/
cp Models/ONNX/yolox_int8.onnx /path/to/android/app/src/main/assets/  # 옵션
```

### 구현 순서:

1. ✅ 데이터 클래스 먼저 (`Feedback.kt`)
2. ✅ RTMPose 추론 (`RTMPoseRunner.kt`)
3. ✅ 프레이밍 분석 (`PhotographyFramingAnalyzer.kt`)
4. ✅ 포즈 비교 (`AdaptivePoseComparator.kt`)
5. ✅ 피드백 생성 (`StagedFeedbackGenerator.kt`)
6. ✅ 파이프라인 통합 (`RealtimeAnalyzer.kt`)

---

**최종 업데이트:** 2025-11-27
**필수 파일 개수:** 6개 (알고리즘 5개 + 데이터 모델 1개)
