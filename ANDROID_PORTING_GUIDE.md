# 📱 Android 포팅 가이드

이 브랜치(`android-port-reference`)는 iOS에서 구현된 TryAngle 포즈 분석 알고리즘을 Android로 포팅하기 위한 참고 자료입니다.

> **⚠️ 주의**: 이 브랜치는 Android 개발자가 참고할 **읽기 전용** 브랜치입니다. iOS 개발은 `main` 브랜치에서 진행됩니다.

---

## 📋 목차

1. [핵심 알고리즘 파일 개요](#핵심-알고리즘-파일-개요)
2. [모델 파일 안내](#모델-파일-안내)
3. [전체 아키텍처](#전체-아키텍처)
4. [각 파일 상세 설명](#각-파일-상세-설명)
5. [Android 구현 가이드](#android-구현-가이드)

---

## 🎯 핵심 알고리즘 파일 개요

총 **5개**의 핵심 알고리즘 파일 (3,938줄):

| 파일명 | 줄 수 | 역할 | 우선순위 |
|--------|------|------|----------|
| **RTMPoseRunner.swift** | 460줄 | ONNX 모델 추론 (133 keypoints 검출) | ⭐⭐⭐ 필수 |
| **PhotographyFramingAnalyzer.swift** | 945줄 | 샷 타입 분류 및 프레이밍 분석 | ⭐⭐⭐ 필수 |
| **AdaptivePoseComparator.swift** | 1,207줄 | 레퍼런스-현재 포즈 비교 | ⭐⭐⭐ 필수 |
| **StagedFeedbackGenerator.swift** | 574줄 | 6단계 피드백 생성 시스템 | ⭐⭐⭐ 필수 |
| **RealtimeAnalyzer.swift** | 752줄 | 실시간 분석 파이프라인 통합 | ⭐⭐ 중요 |

**파일 위치:**
```
ios/TryAngleApp/Services/
├── Analysis/
│   ├── RTMPoseRunner.swift           (ONNX 추론)
│   └── PhotographyFramingAnalyzer.swift (프레이밍 분석)
├── Comparison/
│   ├── AdaptivePoseComparator.swift  (포즈 비교)
│   └── StagedFeedbackGenerator.swift (피드백 생성)
└── RealtimeAnalyzer.swift            (전체 통합)
```

---

## 📦 모델 파일 안내

### ✅ Android에서 그대로 사용 가능한 ONNX 모델

```
ios/TryAngleApp/Models/ONNX/
├── rtmpose_int8.onnx     (218MB) ⭐ RTMPose 133 keypoints 검출용
└── yolox_int8.onnx       (97MB)  ⭐ 사람 검출용 (옵션)
```

**Android 의존성 추가:**
```gradle
// app/build.gradle
dependencies {
    implementation 'com.microsoft.onnxruntime:onnxruntime-android:1.17.0'
}
```

**사용 예시 (Kotlin):**
```kotlin
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession

val env = OrtEnvironment.getEnvironment()
val sessionOptions = OrtSession.SessionOptions()
val session = env.createSession(modelPath, sessionOptions)

// 추론 (자세한 내용은 RTMPoseRunner.swift 참고)
val inputTensor = OnnxTensor.createTensorFromBuffer(...)
val output = session.run(mapOf("input" to inputTensor))
```

### ⚠️ iOS 전용 모델 (변환 필요)

```
ios/TryAngleApp/yolo11s-pose.mlpackage (19MB) - CoreML 전용
```

**대안:**
1. **YOLO11s ONNX 버전 다운로드** (추천)
   - https://github.com/ultralytics/ultralytics
   - `yolo11s-pose.pt` → `yolo11s-pose.onnx` 변환

2. **기존 YOLOX 사용**
   - 이미 제공된 `yolox_int8.onnx` 활용

---

## 🏗️ 전체 아키텍처

```
📸 카메라 프레임
    ↓
┌─────────────────────────────────────────┐
│ 1️⃣ RTMPoseRunner.swift                  │
│    - ONNX 모델로 133개 키포인트 검출      │
│    - 신뢰도(confidence) 필터링           │
└─────────────────────────────────────────┘
    ↓ keypoints: [(x, y, confidence)] × 133
┌─────────────────────────────────────────┐
│ 2️⃣ PhotographyFramingAnalyzer.swift    │
│    - 샷 타입 분류 (클로즈업/풀샷 등)      │
│    - 키포인트 기반 여백 계산              │
│    - 크롭 감지                           │
└─────────────────────────────────────────┘
    ↓ shotType, padding, croppedParts
┌─────────────────────────────────────────┐
│ 3️⃣ AdaptivePoseComparator.swift        │
│    - 레퍼런스 포즈와 현재 포즈 비교        │
│    - 관절 각도 차이 계산                  │
│    - 샷 타입별 키포인트 필터링             │
└─────────────────────────────────────────┘
    ↓ angleDifferences, misalignedParts
┌─────────────────────────────────────────┐
│ 4️⃣ StagedFeedbackGenerator.swift       │
│    - 6단계 우선순위 피드백 생성            │
│    - 전후면 카메라 구분                   │
│    - 자연스러운 한국어 메시지              │
└─────────────────────────────────────────┘
    ↓ feedback: [FeedbackItem]
┌─────────────────────────────────────────┐
│ 5️⃣ RealtimeAnalyzer.swift              │
│    - 전체 파이프라인 통합                 │
│    - 프레임 간 상태 관리                  │
│    - UI 업데이트                         │
└─────────────────────────────────────────┘
    ↓
📱 화면에 피드백 표시
```

---

## 📄 각 파일 상세 설명

### 1️⃣ RTMPoseRunner.swift (460줄)

**역할:** ONNX Runtime을 사용해 RTMPose 모델로 133개 키포인트 검출

**주요 메서드:**
```swift
func detectPose(image: UIImage) -> [(point: CGPoint, confidence: Float)]?
```

**입력:**
- `UIImage`: 카메라 프레임 (288×384 또는 256×192로 리사이즈)

**출력:**
- 133개 키포인트 배열:
  - 인덱스 0-16: Body (17개) - 코, 눈, 귀, 어깨, 팔꿈치, 손목, 엉덩이, 무릎, 발목
  - 인덱스 17-22: Feet (6개) - 발가락
  - 인덱스 23-90: Face (68개) - 얼굴 랜드마크
  - 인덱스 91-111: Left Hand (21개) - 왼손 관절
  - 인덱스 112-132: Right Hand (21개) - 오른손 관절
- 각 키포인트: `(x: CGFloat, y: CGFloat, confidence: Float)`
  - x, y: 0.0 ~ 1.0 정규화된 좌표
  - confidence: 0.0 ~ 1.0 신뢰도 (0.3 이하는 신뢰도 낮음)

**핵심 로직:**
1. 이미지 전처리 (리사이즈, 정규화)
2. ONNX 모델 추론
3. 출력 파싱 (simcc 방식: x좌표, y좌표 히트맵)
4. 신뢰도 필터링

**Android 포팅 시 주의사항:**
- iOS의 `CVPixelBuffer`는 Android의 `Bitmap` 또는 `ByteBuffer`로 대체
- CoreML이 아닌 ONNX Runtime 사용
- 좌표계 변환 주의 (iOS: 좌상단 (0,0), Android: 동일하지만 확인 필요)

---

### 2️⃣ PhotographyFramingAnalyzer.swift (945줄)

**역할:** 사진학 이론 기반 프레이밍 분석 (샷 타입, 여백, 크롭)

**주요 메서드:**
```swift
func analyze(
    keypoints: [(point: CGPoint, confidence: Float)],
    imageSize: CGSize,
    aspectRatio: CameraAspectRatio
) -> PhotographyFramingResult
```

**입력:**
- `keypoints`: RTMPose가 검출한 133개 키포인트
- `imageSize`: 이미지 해상도
- `aspectRatio`: 카메라 비율 (4:3, 16:9, 1:1)

**출력 (`PhotographyFramingResult`):**
```swift
struct PhotographyFramingResult {
    let shotType: ShotType              // 샷 타입
    let padding: ImagePadding           // 여백 정보
    let croppedParts: [KeypointGroup]   // 잘린 부위
    let nosePosition: CGPoint           // 코 위치
    let bodyBoundingBox: CGRect         // 전신 영역
}
```

**샷 타입 분류:**
- `extremeCloseUp`: 극단 클로즈업 (얼굴만)
- `closeUp`: 클로즈업 (머리~어깨)
- `mediumCloseUp`: 미디엄 클로즈업 (머리~가슴)
- `mediumShot`: 미디엄샷 (머리~허리, 상반신)
- `americanShot`: 아메리칸샷 (머리~무릎)
- `fullShot`: 풀샷 (전신)

**핵심 로직:**
1. **키포인트 기반 패딩 계산** (Line 60-165)
   - 구조적 키포인트(0-16)만 사용해 사람이 차지하는 영역 계산
   - 상하좌우 여백 비율 추출

2. **샷 타입 결정** (Line 333-412)
   - 가시적인 키포인트 범위로 샷 타입 분류
   - 예: 무릎(13-14)까지 보이면 americanShot, 발목(15-16)까지면 fullShot

3. **크롭 감지** (Line 453-539)
   - 이미지 경계에서 5% 이내에 있는 키포인트는 "잘림"으로 판단

**Android 포팅 시 주의사항:**
- Swift의 `CGRect`, `CGPoint`는 Android의 `RectF`, `PointF`로 대체
- 모든 좌표는 정규화(0.0~1.0) 상태로 처리

---

### 3️⃣ AdaptivePoseComparator.swift (1,207줄)

**역할:** 레퍼런스 포즈와 현재 포즈 비교 (샷 타입별 적응형)

**주요 메서드:**
```swift
func compare(
    reference: [(point: CGPoint, confidence: Float)],
    current: [(point: CGPoint, confidence: Float)],
    referenceShotType: ShotType,
    currentShotType: ShotType
) -> PoseComparisonResult
```

**입력:**
- `reference`: 레퍼런스 포즈 키포인트 133개
- `current`: 현재 포즈 키포인트 133개
- `referenceShotType`, `currentShotType`: 각각의 샷 타입

**출력 (`PoseComparisonResult`):**
```swift
struct PoseComparisonResult {
    let angleDifferences: [String: Float]       // 각도 차이 (도 단위)
    let angleDirections: [String: String]       // 교정 방향 설명
    let positionDifferences: [String: CGPoint]  // 위치 차이
    let overallSimilarity: Float                // 전체 유사도 (0~1)
    let misalignedParts: [String]               // 어긋난 부위들
}
```

**핵심 로직:**

1. **샷 타입별 키포인트 필터링** (Line 196-235)
   ```swift
   func getRequiredKeypoints(for shotType: ShotType) -> [Int] {
       switch shotType {
       case .mediumShot:  // 상반신
           // 몸통(0-12) + 얼굴(23-90) + 손(91-132)
           return Array(0...12) + Array(23...90) + Array(91...132)
       case .fullShot:    // 전신
           return Array(0...132)  // 모든 키포인트
       // ...
       }
   }
   ```

2. **관절 각도 계산** (Line 460-680)
   - 팔꿈치 각도: 어깨-팔꿈치-손목 3점으로 계산
   - 무릎 각도: 엉덩이-무릎-발목 3점으로 계산
   - 어깨 기울기: 양쪽 어깨 수평선 각도
   - **15도 이상 차이 → 피드백 생성**

3. **각도 차이 방향 계산** (Line 550-680)
   ```swift
   if currentAngle < referenceAngle - 15 {
       angleDirections["left_elbow"] = "왼팔을 더 펴세요"
   } else if currentAngle > referenceAngle + 15 {
       angleDirections["left_elbow"] = "왼팔을 더 구부리세요"
   }
   ```

4. **전체 유사도 계산** (Line 870-980)
   - 각 관절의 각도 차이를 점수로 환산
   - 0.0 (완전히 다름) ~ 1.0 (완벽히 일치)

**Android 포팅 시 주의사항:**
- `atan2()` 함수로 각도 계산 (라디안 → 도 변환 필요)
- 벡터 내적으로 각도 계산: `acos(dot(v1, v2))`
- Swift의 `simd` 라이브러리는 Kotlin의 벡터 연산으로 대체

---

### 4️⃣ StagedFeedbackGenerator.swift (574줄)

**역할:** 6단계 우선순위 피드백 생성 (한국어, 전후면 카메라 구분)

**주요 메서드:**
```swift
func generateFeedback(
    referenceFraming: PhotographyFramingResult?,
    currentFraming: PhotographyFramingResult?,
    poseComparison: PoseComparisonResult?,
    isFrontCamera: Bool,
    aspectRatio: CameraAspectRatio
) -> [FeedbackItem]
```

**입력:**
- `referenceFraming`: 레퍼런스 프레이밍 분석 결과
- `currentFraming`: 현재 프레이밍 분석 결과
- `poseComparison`: 포즈 비교 결과
- `isFrontCamera`: 전면 카메라 여부 (셀카 모드)
- `aspectRatio`: 카메라 비율

**출력:**
- `[FeedbackItem]`: 우선순위 정렬된 피드백 리스트
  ```swift
  struct FeedbackItem {
      let stage: Int          // 1~6 단계
      let message: String     // "카메라를 위로 올려주세요"
      let severity: Float     // 0.0~1.0 심각도
      let icon: String        // "📸", "📏", "🤸" 등
  }
  ```

**6단계 피드백 우선순위:**

```
Stage 1: 📸 비율 불일치 (가장 높음)
   - "카메라 비율을 4:3으로 변경하세요"

Stage 2: 📏 샷 타입 불일치
   - "카메라를 뒤로 멀리하세요 (전신이 보이게)"
   - 전면 카메라: "뒤로 물러나세요"

Stage 3: 🔲 크롭 감지
   - "다리가 잘렸어요. 카메라를 뒤로 멀리하세요"
   - "손이 잘렸어요. 왼쪽으로 이동하세요"

Stage 4: 📐 커버리지 불일치
   - "카메라를 가까이 당기세요"
   - "뒤로 물러나세요"

Stage 5: 📍 위치 불일치
   - 상하: "카메라를 위로/아래로"
   - 좌우: "왼쪽/오른쪽으로 이동하세요"

Stage 6: 🤸 포즈 차이 (가장 낮음)
   - "왼팔을 더 펴세요 (15° 차이)"
   - "몸을 왼쪽으로 기울이세요"
   - "왼쪽 무릎을 더 구부리세요"
```

**전후면 카메라 구분 로직:**
```swift
// Stage 2: 샷 타입 피드백 (Line 289-324)
if isFrontCamera {
    message = "뒤로 물러나세요 (전신이 보이게)"  // 사람이 움직임
} else {
    message = "카메라를 뒤로 멀리하세요"         // 카메라를 움직임
}

// Stage 4: 커버리지 피드백 (Line 326-354)
if coverageDiff > 0 {
    message = isFrontCamera ? "뒤로 물러나세요" : "카메라를 뒤로 멀리하세요"
}

// Stage 5: 위치 피드백 (Line 351-403)
// 상하: 항상 카메라 조작
message = yDiff > 0 ? "카메라를 아래로" : "카메라를 위로"
// 좌우: 사람이 이동
message = xDiff > 0 ? "왼쪽으로 이동하세요" : "오른쪽으로 이동하세요"
```

**Android 포팅 시 주의사항:**
- 한국어 메시지는 그대로 사용 가능
- 전후면 카메라 구분 로직 필수 구현
- 피드백 우선순위 정렬 중요 (Stage 1 → 6 순서)

---

### 5️⃣ RealtimeAnalyzer.swift (752줄)

**역할:** 전체 실시간 분석 파이프라인 통합 및 상태 관리

**주요 메서드:**
```swift
func processFrame(
    image: UIImage,
    referenceKeypoints: [(point: CGPoint, confidence: Float)]?,
    isFrontCamera: Bool,
    aspectRatio: CameraAspectRatio
)
```

**실행 흐름:**
```swift
// 1. RTMPose로 키포인트 검출
let currentKeypoints = rtmPoseRunner.detectPose(image: image)

// 2. 프레이밍 분석
let currentFraming = photographyFramingAnalyzer.analyze(
    keypoints: currentKeypoints,
    imageSize: image.size,
    aspectRatio: aspectRatio
)

// 3. 레퍼런스와 비교
let poseComparison = adaptivePoseComparator.compare(
    reference: referenceKeypoints,
    current: currentKeypoints,
    referenceShotType: referenceShotType,
    currentShotType: currentFraming.shotType
)

// 4. 피드백 생성
let feedback = stagedFeedbackGenerator.generateFeedback(
    referenceFraming: referenceFraming,
    currentFraming: currentFraming,
    poseComparison: poseComparison,
    isFrontCamera: isFrontCamera,
    aspectRatio: aspectRatio
)

// 5. UI 업데이트
self.currentFeedback = feedback
```

**프레임 간 상태 관리:**
- 이전 프레임 결과 캐싱
- 떨림 방지 (같은 피드백이 3프레임 연속 → 확정)
- 완성도 점수 계산 (0.0 ~ 1.0)

**Android 포팅 시 주의사항:**
- `@Published` → Android의 `LiveData` 또는 `StateFlow`
- 메인 스레드에서 UI 업데이트
- 프레임 드롭 방지 (비동기 처리)

---

## 🤖 Android 구현 가이드

### 1단계: ONNX Runtime 설정

```kotlin
// app/build.gradle
dependencies {
    implementation 'com.microsoft.onnxruntime:onnxruntime-android:1.17.0'
}

// assets/ 폴더에 모델 복사
// app/src/main/assets/rtmpose_int8.onnx
```

### 2단계: 데이터 클래스 정의

```kotlin
// Keypoint.kt
data class Keypoint(
    val x: Float,  // 0.0 ~ 1.0
    val y: Float,  // 0.0 ~ 1.0
    val confidence: Float  // 0.0 ~ 1.0
)

// ShotType.kt
enum class ShotType {
    EXTREME_CLOSE_UP,
    CLOSE_UP,
    MEDIUM_CLOSE_UP,
    MEDIUM_SHOT,
    AMERICAN_SHOT,
    FULL_SHOT
}

// FeedbackItem.kt
data class FeedbackItem(
    val stage: Int,       // 1~6
    val message: String,  // "카메라를 위로 올려주세요"
    val severity: Float,  // 0.0~1.0
    val icon: String      // "📸"
)
```

### 3단계: 각 Swift 파일을 Kotlin으로 변환

**변환 순서 (권장):**
1. ✅ RTMPoseRunner.swift → `RTMPoseRunner.kt`
2. ✅ PhotographyFramingAnalyzer.swift → `PhotographyFramingAnalyzer.kt`
3. ✅ AdaptivePoseComparator.swift → `AdaptivePoseComparator.kt`
4. ✅ StagedFeedbackGenerator.swift → `StagedFeedbackGenerator.kt`
5. ✅ RealtimeAnalyzer.swift → `RealtimeAnalyzer.kt`

**변환 팁:**
- Swift의 `struct` → Kotlin의 `data class`
- Swift의 `class` → Kotlin의 `class`
- Swift의 `enum` → Kotlin의 `enum class`
- Swift의 `func` → Kotlin의 `fun`
- Swift의 `CGPoint`, `CGRect` → Kotlin의 `PointF`, `RectF`
- Swift의 `atan2()` → Kotlin의 `kotlin.math.atan2()`

### 4단계: 카메라 통합

```kotlin
// CameraManager.kt
class CameraManager(context: Context) {
    private val rtmPoseRunner = RTMPoseRunner(context)
    private val realtimeAnalyzer = RealtimeAnalyzer()

    fun analyzeFrame(
        bitmap: Bitmap,
        isFrontCamera: Boolean
    ): List<FeedbackItem> {
        return realtimeAnalyzer.processFrame(
            image = bitmap,
            isFrontCamera = isFrontCamera
        )
    }
}
```

### 5단계: UI 표시

```kotlin
// FeedbackOverlay.kt
@Composable
fun FeedbackOverlay(feedbacks: List<FeedbackItem>) {
    Column {
        feedbacks.forEach { feedback ->
            Text(
                text = "${feedback.icon} ${feedback.message}",
                color = when (feedback.stage) {
                    1, 2, 3 -> Color.Red      // 높은 우선순위
                    4, 5 -> Color.Yellow       // 중간 우선순위
                    6 -> Color.Green           // 낮은 우선순위
                    else -> Color.White
                }
            )
        }
    }
}
```

---

## 📚 참고 자료

### Swift → Kotlin 주요 차이점

| Swift | Kotlin | 설명 |
|-------|--------|------|
| `CGPoint` | `PointF` | 2D 좌표 |
| `CGRect` | `RectF` | 사각형 영역 |
| `CGFloat` | `Float` | 부동소수점 |
| `UIImage` | `Bitmap` | 이미지 |
| `atan2(y, x)` | `atan2(y, x)` | 각도 계산 (동일) |
| `Array<T>` | `List<T>` | 배열 |
| `[String: Float]` | `Map<String, Float>` | 딕셔너리 |
| `@Published` | `StateFlow` | 상태 관리 |

### 수학 함수

```kotlin
import kotlin.math.*

// 벡터 크기
fun magnitude(x: Float, y: Float) = sqrt(x*x + y*y)

// 두 점 사이 거리
fun distance(p1: PointF, p2: PointF): Float {
    val dx = p2.x - p1.x
    val dy = p2.y - p1.y
    return sqrt(dx*dx + dy*dy)
}

// 세 점으로 각도 계산
fun angle(p1: PointF, vertex: PointF, p3: PointF): Float {
    val v1x = p1.x - vertex.x
    val v1y = p1.y - vertex.y
    val v2x = p3.x - vertex.x
    val v2y = p3.y - vertex.y

    val dot = v1x * v2x + v1y * v2y
    val mag1 = sqrt(v1x*v1x + v1y*v1y)
    val mag2 = sqrt(v2x*v2x + v2y*v2y)

    val cosAngle = dot / (mag1 * mag2)
    return Math.toDegrees(acos(cosAngle).toDouble()).toFloat()
}
```

---

## ❓ FAQ

### Q1: RTMPose 모델은 어디서 구하나요?
**A:** 이미 제공된 `rtmpose_int8.onnx` (218MB) 사용. iOS 프로젝트의 `ios/TryAngleApp/Models/ONNX/` 폴더에 있습니다.

### Q2: 샷 타입 분류가 정확하지 않으면?
**A:** `PhotographyFramingAnalyzer.swift`의 Line 333-412에서 임계값 조정 가능. 예: `headHeight * 6.0` → `headHeight * 5.5`

### Q3: 피드백 메시지를 영어로 바꾸려면?
**A:** `StagedFeedbackGenerator.swift`의 모든 한국어 문자열을 영어로 교체. 로직은 동일.

### Q4: 전면/후면 카메라 구분이 왜 필요한가요?
**A:** 셀카 모드(전면)에서는 팔 길이 제한으로 "카메라를 뒤로"가 불가능 → "뒤로 물러나세요"로 변경.

### Q5: 133개 키포인트가 너무 많으면?
**A:** `AdaptivePoseComparator.swift`의 `getRequiredKeypoints()`에서 샷 타입별로 필터링됨. 상반신 샷은 손/얼굴만, 풀샷은 전체.

---

## 📞 문의

Android 포팅 중 문제가 발생하면:
1. Swift 코드의 주석 참고
2. 각 함수의 입출력 확인
3. iOS 개발자에게 문의

---

## 📝 라이선스

이 알고리즘은 TryAngle 프로젝트의 일부입니다.

---

**최종 업데이트:** 2025-11-27
**iOS 버전:** fdb39d4
**Android 포팅 상태:** 준비 완료
