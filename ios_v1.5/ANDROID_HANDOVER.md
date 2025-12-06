# 🤖 Android 개발자 인수인계 문서

> **TryAngle v1.5 온디바이스 분석 시스템**
>
> 작성일: 2025-12-06
> iOS 브랜치: `feature/ios-v1.5-ondevice-optimization`

---

## 📋 목차

1. [시스템 아키텍처 개요](#1-시스템-아키텍처-개요)
2. [필수 모델 파일](#2-필수-모델-파일)
3. [핵심 파일 목록 및 설명](#3-핵심-파일-목록-및-설명)
4. [알고리즘 상세 설명](#4-알고리즘-상세-설명)
5. [데이터 구조](#5-데이터-구조)
6. [안드로이드 변환 가이드](#6-안드로이드-변환-가이드)

---

## 1. 시스템 아키텍처 개요

### 1.1 레벨별 처리 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                    실시간 분석 파이프라인                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: RTMPose (매 프레임)                                    │
│  ├── YOLOX: 사람 검출 (640x640)                                  │
│  └── RTMPose: 133개 키포인트 추출 (192x256)                       │
│                                                                 │
│  Level 2: Depth (5프레임마다)                                     │
│  └── 얼굴 크기 기반 거리/압축감 추정                                │
│                                                                 │
│  Level 3: Grounding DINO (30프레임마다)                          │
│  └── 정밀 바운딩 박스 검출 (800x800)                               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                     Gate System (4단계 평가)                      │
│  Gate 1: 여백 균형 (threshold: 70%)                              │
│  Gate 2: 프레이밍 (threshold: 65%)                               │
│  Gate 3: 구도 (threshold: 70%)                                   │
│  Gate 4: 압축감 (threshold: 60%)                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 발열 상태 기반 동적 프레임 스킵

| 발열 상태 | Level 1 | Level 2 | Level 3 | 분석 간격 |
|-----------|---------|---------|---------|-----------|
| nominal   | 1프레임 | 5프레임 | 30프레임 | 16ms (60fps) |
| fair      | 1프레임 | 5프레임 | 30프레임 | 16ms |
| serious   | 2프레임 | 10프레임 | 60프레임 | 22ms (45fps) |
| critical  | 3프레임 | 15프레임 | 90프레임 | 33ms (30fps) |

---

## 2. 필수 모델 파일

### 2.1 ONNX 모델 (필수)

| 모델 | 파일명 | 크기 | 다운로드 링크 |
|------|--------|------|---------------|
| YOLOX (사람 검출) | `yolox_int8.onnx` | 97MB | [RTMDet-ONNX](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose) |
| RTMPose (포즈 추정) | `rtmpose_int8.onnx` | 218MB | [RTMPose-ONNX](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose) |
| Grounding DINO | `grounding_dino.onnx` | 194MB | [HuggingFace](https://huggingface.co/onnx-community/grounding-dino-tiny-ONNX) |

### 2.2 모델 입력/출력 스펙

#### YOLOX (사람 검출)
```
입력: "input" - [1, 3, 640, 640] float32 (RGB, ImageNet 정규화)
출력:
  - "dets" - [1, N, 5] float32 (x1, y1, x2, y2, score)
  - "labels" - [1, N] int64 (class_id, person=0)
```

#### RTMPose (포즈 추정)
```
입력: "input" - [1, 3, 256, 192] float32 (RGB, ImageNet 정규화)
출력:
  - "simcc_x" - [1, 133, 384] float32 (x좌표 확률분포)
  - "simcc_y" - [1, 133, 512] float32 (y좌표 확률분포)
```

#### Grounding DINO
```
입력:
  - "pixel_values" - [1, 3, 800, 800] float32
  - "pixel_mask" - [1, 800, 800] int64
  - "input_ids" - [1, 3] int64 ([101, 2711, 102] = "person")
  - "attention_mask" - [1, 3] int64
  - "token_type_ids" - [1, 3] int64
출력:
  - "logits" - [1, 900, 1] float32
  - "pred_boxes" - [1, 900, 4] float32 (cx, cy, w, h normalized)
```

---

## 3. 핵심 파일 목록 및 설명

### 3.1 🔴 반드시 변환해야 할 핵심 파일 (우선순위 순)

```
ios_v1.5/TryAngleApp/Services/
├── OnDevice/                          # ⭐ 온디바이스 분석 핵심
│   ├── GateSystem.swift               # ⭐⭐⭐ Gate 평가 로직 (필수)
│   ├── MarginAnalyzer.swift           # ⭐⭐⭐ 여백 분석 (필수)
│   ├── GroundingDINOONNX.swift        # ⭐⭐ ONNX 추론 (필수)
│   ├── GroundingDINOCoreML.swift      # ⭐⭐ 통합 인터페이스
│   ├── V15FeedbackGenerator.swift     # ⭐⭐ 피드백 생성
│   ├── PerformanceOptimizer.swift     # ⭐ 성능 최적화
│   ├── CacheManager.swift             # 캐시 관리
│   └── TryAngleOnDeviceAnalyzer.swift # 통합 분석기
│
├── Analysis/                          # 분석 모듈
│   ├── RTMPoseRunner.swift            # ⭐⭐⭐ ONNX 포즈 추정 (필수)
│   ├── PoseMLAnalyzer.swift           # 포즈 분석 래퍼
│   ├── DepthEstimator.swift           # 거리/압축감 추정
│   ├── PhotographyFramingAnalyzer.swift # 사진학 프레이밍
│   └── GazeTracker.swift              # 시선 추적
│
├── Comparison/                        # 비교 분석
│   ├── AdaptivePoseComparator.swift   # ⭐⭐ 포즈 비교 (필수)
│   ├── StagedFeedbackGenerator.swift  # 단계별 피드백
│   ├── GapAnalyzer.swift              # 차이 분석
│   └── FeedbackGenerator.swift        # 피드백 생성
│
├── RuleEngine/                        # 규칙 엔진
│   ├── CameraAngleDetector.swift      # 카메라 앵글 감지
│   └── CompositionAnalyzer.swift      # 구도 분석
│
├── RealtimeAnalyzer.swift             # ⭐⭐⭐ 실시간 통합 (필수)
├── ThermalStateManager.swift          # 발열 관리
└── CameraManager.swift                # 카메라 관리
```

### 3.2 데이터 모델 파일

```
ios_v1.5/TryAngleApp/Models/
└── Feedback.swift                     # ⭐⭐⭐ 모든 데이터 구조 정의 (필수)
```

---

## 4. 알고리즘 상세 설명

### 4.1 GateSystem.swift (⭐⭐⭐ 핵심)

```kotlin
// 안드로이드 변환 예시 (Kotlin)

data class GateResult(
    val passed: Boolean,
    val score: Float,       // 0.0 ~ 1.0
    val threshold: Float,
    val feedback: String
)

data class GateEvaluation(
    val gate1: GateResult,  // 여백 균형
    val gate2: GateResult,  // 프레이밍
    val gate3: GateResult,  // 구도
    val gate4: GateResult,  // 압축감
    val overallScore: Float,
    val allPassed: Boolean,
    val primaryFeedback: String
)

class GateSystem {
    companion object {
        // Gate 임계값
        const val MARGIN_THRESHOLD = 0.70f
        const val FRAMING_THRESHOLD = 0.65f
        const val COMPOSITION_THRESHOLD = 0.70f
        const val COMPRESSION_THRESHOLD = 0.60f
    }

    fun evaluate(
        currentBBox: RectF,
        referenceBBox: RectF,
        currentImageSize: Size,
        referenceImageSize: Size,
        compressionIndex: Float?,
        referenceCompressionIndex: Float?
    ): GateEvaluation {
        // 구현 내용은 GateSystem.swift 참조
    }
}
```

### 4.2 MarginAnalyzer.swift (⭐⭐⭐ 핵심)

```kotlin
// 여백 분석 결과
data class MarginAnalysisResult(
    val left: Float,
    val right: Float,
    val top: Float,
    val bottom: Float,
    val horizontalBalance: Float,  // 좌우 균형 (0.0 ~ 1.0)
    val verticalBalance: Float,    // 상하 균형 (0.0 ~ 1.0)
    val overallScore: Float,
    val movementDirection: MovementDirection?
)

// 움직임 방향 피드백
data class MovementDirection(
    val horizontal: Float,  // -1.0(왼쪽) ~ 1.0(오른쪽)
    val vertical: Float,    // -1.0(위) ~ 1.0(아래)
    val primaryArrow: String,
    val description: String
)

class MarginAnalyzer {
    fun analyze(
        bbox: RectF,
        imageSize: Size,
        isNormalized: Boolean = true
    ): MarginAnalysisResult {
        // 정규화 좌표 (0.0 ~ 1.0) 가정
        val left = bbox.left
        val right = 1.0f - bbox.right
        val top = 1.0f - bbox.bottom  // Y축 반전 주의
        val bottom = bbox.top

        // 좌우 균형 점수 (같을수록 1.0)
        val horizontalBalance = 1.0f - abs(left - right) * 2

        // 상하 균형 점수 (상단 여백이 더 작아야 함 - 2:1 비율 선호)
        val idealTopRatio = 0.33f
        val verticalBalance = 1.0f - abs(top / (top + bottom) - idealTopRatio) * 3

        // 종합 점수
        val overallScore = (horizontalBalance * 0.5f + verticalBalance * 0.5f)
            .coerceIn(0.0f, 1.0f)

        return MarginAnalysisResult(...)
    }
}
```

### 4.3 RTMPoseRunner.swift (⭐⭐⭐ 핵심)

```kotlin
// 133개 키포인트 인덱스
object RTMPoseKeypoints {
    // 몸통 (0-16)
    const val NOSE = 0
    const val LEFT_EYE = 1
    const val RIGHT_EYE = 2
    const val LEFT_EAR = 3
    const val RIGHT_EAR = 4
    const val LEFT_SHOULDER = 5
    const val RIGHT_SHOULDER = 6
    const val LEFT_ELBOW = 7
    const val RIGHT_ELBOW = 8
    const val LEFT_WRIST = 9
    const val RIGHT_WRIST = 10
    const val LEFT_HIP = 11
    const val RIGHT_HIP = 12
    const val LEFT_KNEE = 13
    const val RIGHT_KNEE = 14
    const val LEFT_ANKLE = 15
    const val RIGHT_ANKLE = 16

    // 발 (17-22)
    const val LEFT_BIG_TOE = 17
    const val LEFT_SMALL_TOE = 18
    const val LEFT_HEEL = 19
    const val RIGHT_BIG_TOE = 20
    const val RIGHT_SMALL_TOE = 21
    const val RIGHT_HEEL = 22

    // 얼굴 (23-90): 68개 랜드마크
    val FACE_RANGE = 23..90

    // 왼손 (91-111): 21개 관절
    val LEFT_HAND_RANGE = 91..111

    // 오른손 (112-132): 21개 관절
    val RIGHT_HAND_RANGE = 112..132
}

class RTMPoseRunner(context: Context) {
    private val ortEnv = OrtEnvironment.getEnvironment()
    private val yoloxSession: OrtSession
    private val poseSession: OrtSession

    init {
        // ONNX Runtime 세션 생성
        val sessionOptions = OrtSession.SessionOptions().apply {
            // NNAPI 가속 (Android)
            addNnapi()
            setIntraOpNumThreads(6)
            setGraphOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        }

        yoloxSession = ortEnv.createSession(loadModel("yolox_int8.onnx"), sessionOptions)
        poseSession = ortEnv.createSession(loadModel("rtmpose_int8.onnx"), sessionOptions)
    }

    fun detectPose(bitmap: Bitmap): List<Keypoint>? {
        // 1. YOLOX로 사람 검출
        val bbox = detectPerson(bitmap) ?: return null

        // 2. 바운딩 박스 영역 크롭 (40% 패딩)
        val croppedBitmap = cropWithPadding(bitmap, bbox, padding = 0.4f)

        // 3. 192x256으로 리사이즈
        val resizedBitmap = Bitmap.createScaledBitmap(croppedBitmap, 192, 256, true)

        // 4. 이미지 정규화 (ImageNet)
        val inputTensor = preprocessImage(resizedBitmap)

        // 5. 추론
        val outputs = poseSession.run(mapOf("input" to inputTensor))

        // 6. SimCC 출력 파싱
        return parseSimCCOutput(outputs, bbox)
    }

    private fun preprocessImage(bitmap: Bitmap): OnnxTensor {
        val mean = floatArrayOf(0.485f, 0.456f, 0.406f)
        val std = floatArrayOf(0.229f, 0.224f, 0.225f)

        val pixels = IntArray(192 * 256)
        bitmap.getPixels(pixels, 0, 192, 0, 0, 192, 256)

        val floatBuffer = FloatBuffer.allocate(3 * 256 * 192)

        for (c in 0..2) {
            for (i in pixels.indices) {
                val pixel = pixels[i]
                val value = when (c) {
                    0 -> (pixel shr 16 and 0xFF) / 255f
                    1 -> (pixel shr 8 and 0xFF) / 255f
                    else -> (pixel and 0xFF) / 255f
                }
                floatBuffer.put(c * 256 * 192 + i, (value - mean[c]) / std[c])
            }
        }

        return OnnxTensor.createTensor(ortEnv, floatBuffer, longArrayOf(1, 3, 256, 192))
    }

    private fun parseSimCCOutput(outputs: OrtSession.Result, bbox: RectF): List<Keypoint> {
        val simccX = outputs["simcc_x"].get().value as Array<Array<FloatArray>>
        val simccY = outputs["simcc_y"].get().value as Array<Array<FloatArray>>

        val keypoints = mutableListOf<Keypoint>()

        for (i in 0 until 133) {
            // argmax로 최대값 인덱스 찾기
            val xIdx = simccX[0][i].indices.maxByOrNull { simccX[0][i][it] } ?: 0
            val yIdx = simccY[0][i].indices.maxByOrNull { simccY[0][i][it] } ?: 0

            // SimCC 좌표를 픽셀 좌표로 변환
            val x = xIdx.toFloat() / 384f * 192f
            val y = yIdx.toFloat() / 512f * 256f

            // 바운딩 박스 기준으로 원본 이미지 좌표로 변환
            val realX = bbox.left + (x / 192f) * bbox.width()
            val realY = bbox.top + (y / 256f) * bbox.height()

            // 신뢰도 계산
            val confidence = (simccX[0][i][xIdx] + simccY[0][i][yIdx]) / 2f

            keypoints.add(Keypoint(realX, realY, confidence))
        }

        return keypoints
    }
}
```

### 4.4 AdaptivePoseComparator.swift (⭐⭐ 중요)

```kotlin
data class PoseComparisonResult(
    val overallSimilarity: Float,      // 0.0 ~ 1.0
    val bodyAngleSimilarity: Float,
    val limbPositionSimilarity: Float,
    val missingGroups: List<KeypointGroup>,
    val mismatchedJoints: List<Int>
)

enum class KeypointGroup {
    HEAD, TORSO, LEFT_ARM, RIGHT_ARM, LEFT_LEG, RIGHT_LEG, LEFT_HAND, RIGHT_HAND
}

class AdaptivePoseComparator {

    // 키포인트 그룹 정의
    private val groupIndices = mapOf(
        KeypointGroup.HEAD to listOf(0, 1, 2, 3, 4),
        KeypointGroup.TORSO to listOf(5, 6, 11, 12),
        KeypointGroup.LEFT_ARM to listOf(5, 7, 9),
        KeypointGroup.RIGHT_ARM to listOf(6, 8, 10),
        KeypointGroup.LEFT_LEG to listOf(11, 13, 15),
        KeypointGroup.RIGHT_LEG to listOf(12, 14, 16),
        KeypointGroup.LEFT_HAND to (91..111).toList(),
        KeypointGroup.RIGHT_HAND to (112..132).toList()
    )

    fun comparePoses(
        referenceKeypoints: List<Keypoint>,
        currentKeypoints: List<Keypoint>,
        confidenceThreshold: Float = 0.3f
    ): PoseComparisonResult {

        // 1. 유효한 키포인트만 필터링
        val validRefIndices = referenceKeypoints.indices
            .filter { referenceKeypoints[it].confidence >= confidenceThreshold }
        val validCurIndices = currentKeypoints.indices
            .filter { currentKeypoints[it].confidence >= confidenceThreshold }

        // 2. 공통 키포인트로 정규화
        val commonIndices = validRefIndices.intersect(validCurIndices.toSet())

        // 3. 각도 유사도 계산 (팔, 다리 각도)
        val bodyAngleSimilarity = calculateAngleSimilarity(
            referenceKeypoints, currentKeypoints, commonIndices
        )

        // 4. 상대 위치 유사도
        val limbPositionSimilarity = calculatePositionSimilarity(
            referenceKeypoints, currentKeypoints, commonIndices
        )

        // 5. 누락된 그룹 감지
        val missingGroups = detectMissingGroups(
            referenceKeypoints, currentKeypoints, confidenceThreshold
        )

        // 6. 종합 유사도
        val overallSimilarity = (bodyAngleSimilarity * 0.6f + limbPositionSimilarity * 0.4f)
            .coerceIn(0f, 1f)

        return PoseComparisonResult(
            overallSimilarity = overallSimilarity,
            bodyAngleSimilarity = bodyAngleSimilarity,
            limbPositionSimilarity = limbPositionSimilarity,
            missingGroups = missingGroups,
            mismatchedJoints = findMismatchedJoints(referenceKeypoints, currentKeypoints)
        )
    }

    private fun calculateAngleSimilarity(
        ref: List<Keypoint>,
        cur: List<Keypoint>,
        indices: Set<Int>
    ): Float {
        // 팔꿈치 각도 (5-7-9, 6-8-10)
        // 무릎 각도 (11-13-15, 12-14-16)
        // 각 관절의 각도 차이 계산 후 유사도로 변환
        // 구현 상세는 AdaptivePoseComparator.swift 참조
        return 0.8f  // 예시
    }
}
```

---

## 5. 데이터 구조

### 5.1 Feedback.swift 에서 가져올 구조체

```kotlin
// 카메라 비율
enum class CameraAspectRatio(val displayName: String, val ratio: Float) {
    RATIO_16_9("16:9", 16f / 9f),
    RATIO_4_3("4:3", 4f / 3f),
    RATIO_1_1("1:1", 1f);

    companion object {
        fun detect(size: Size): CameraAspectRatio {
            val longSide = maxOf(size.width, size.height).toFloat()
            val shortSide = minOf(size.width, size.height).toFloat()
            val ratio = longSide / shortSide

            return values().minByOrNull { abs(it.ratio - ratio) } ?: RATIO_4_3
        }
    }
}

// 피드백 카테고리
enum class FeedbackCategory(val priority: Int, val displayName: String) {
    POSE(1, "포즈"),
    POSITION(2, "인물 위치"),
    FRAMING(3, "프레이밍"),
    ANGLE(4, "카메라 앵글"),
    COMPOSITION(5, "구도"),
    GAZE(6, "시선");

    companion object {
        fun from(categoryString: String): FeedbackCategory? {
            return when {
                categoryString.startsWith("v15_margin") -> POSITION
                categoryString.startsWith("v15_framing") -> FRAMING
                categoryString.startsWith("v15_composition") -> COMPOSITION
                categoryString.startsWith("v15_compression") -> FRAMING
                categoryString.startsWith("pose_") -> POSE
                else -> null
            }
        }
    }
}

// 피드백 아이템
data class FeedbackItem(
    val priority: Int,
    val icon: String,
    val message: String,
    val category: String,
    val currentValue: Double?,
    val targetValue: Double?,
    val tolerance: Double?,
    val unit: String?
)

// 카테고리 상태 (UI 체크표시용)
data class CategoryStatus(
    val category: FeedbackCategory,
    val isSatisfied: Boolean,
    val activeFeedbacks: List<FeedbackItem>
)
```

---

## 6. 안드로이드 변환 가이드

### 6.1 ONNX Runtime 설정

```gradle
// build.gradle (app)
dependencies {
    implementation 'com.microsoft.onnxruntime:onnxruntime-android:1.16.3'
}
```

### 6.2 모델 파일 위치

```
app/src/main/assets/
├── yolox_int8.onnx        (97MB)
├── rtmpose_int8.onnx      (218MB)
└── grounding_dino.onnx    (194MB)
```

### 6.3 이미지 전처리 최적화

```kotlin
// RenderScript 또는 Vulkan Compute Shader 활용 권장
// iOS의 Accelerate/vDSP 대신 Android에서는:
// 1. RenderScript (deprecated but fast)
// 2. Vulkan Compute Shader
// 3. NDK + NEON intrinsics
```

### 6.4 파일별 변환 우선순위

| 순위 | iOS 파일 | 설명 | 난이도 |
|------|----------|------|--------|
| 1 | `GateSystem.swift` | 핵심 평가 로직 | ⭐ 쉬움 |
| 2 | `MarginAnalyzer.swift` | 여백 분석 | ⭐ 쉬움 |
| 3 | `RTMPoseRunner.swift` | ONNX 포즈 추정 | ⭐⭐⭐ 어려움 |
| 4 | `GroundingDINOONNX.swift` | ONNX 객체 검출 | ⭐⭐ 중간 |
| 5 | `AdaptivePoseComparator.swift` | 포즈 비교 | ⭐⭐ 중간 |
| 6 | `V15FeedbackGenerator.swift` | 피드백 생성 | ⭐ 쉬움 |
| 7 | `RealtimeAnalyzer.swift` | 통합 관리 | ⭐⭐⭐ 어려움 |
| 8 | `PerformanceOptimizer.swift` | 성능 최적화 | ⭐⭐ 중간 |

### 6.5 주의사항

1. **좌표계 차이**: iOS Vision은 Y축이 아래에서 위로 (0=하단, 1=상단). Android는 반대일 수 있음
2. **이미지 회전**: 카메라 회전 처리 확인 필요
3. **발열 관리**: Android의 `PowerManager` 활용
4. **메모리 관리**: 큰 모델이므로 메모리 릭 주의

---

## 📞 연락처

iOS 개발 관련 질문: [이 문서가 포함된 브랜치의 코드 참조]

---

*이 문서는 Claude Code로 자동 생성되었습니다.*
