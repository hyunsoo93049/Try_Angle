# 🤖 ONNX 모델 파일 정보

## 📦 모델 파일 목록

### 1. RTMPose (필수 ⭐⭐⭐)

**파일명:** `rtmpose_int8.onnx`
**크기:** 218 MB
**위치:** `ios/TryAngleApp/Models/ONNX/rtmpose_int8.onnx`

**용도:**
- 133개 키포인트 검출 (Body 17 + Feet 6 + Face 68 + Left Hand 21 + Right Hand 21)
- 전신 포즈 추정

**입력:**
- 형식: `float32`
- Shape: `[1, 3, 288, 384]` (NCHW)
- 범위: 0.0 ~ 1.0 (정규화된 RGB)
- 전처리:
  ```
  mean = [0.485, 0.456, 0.406]
  std = [0.229, 0.224, 0.225]
  normalized_pixel = (pixel / 255.0 - mean) / std
  ```

**출력:**
- `simcc_x`: Shape `[1, 133, 384]` - x좌표 히트맵
- `simcc_y`: Shape `[1, 133, 288]` - y좌표 히트맵
- 후처리: argmax로 최대값 인덱스 추출 → 좌표 변환

**Android 코드 예시:**
```kotlin
// 1. 이미지 전처리
fun preprocessImage(bitmap: Bitmap): FloatArray {
    val resized = Bitmap.createScaledBitmap(bitmap, 384, 288, true)
    val input = FloatArray(1 * 3 * 288 * 384)

    val mean = floatArrayOf(0.485f, 0.456f, 0.406f)
    val std = floatArrayOf(0.229f, 0.224f, 0.225f)

    var idx = 0
    for (c in 0..2) {  // RGB 채널
        for (h in 0 until 288) {
            for (w in 0 until 384) {
                val pixel = resized.getPixel(w, h)
                val value = when (c) {
                    0 -> Color.red(pixel)
                    1 -> Color.green(pixel)
                    else -> Color.blue(pixel)
                } / 255.0f

                input[idx++] = (value - mean[c]) / std[c]
            }
        }
    }
    return input
}

// 2. ONNX 추론
fun detectKeypoints(bitmap: Bitmap): List<Keypoint> {
    val inputTensor = OnnxTensor.createTensor(
        env,
        preprocessImage(bitmap),
        longArrayOf(1, 3, 288, 384)
    )

    val outputs = session.run(mapOf("input" to inputTensor))
    val simccX = outputs[0].value as Array<Array<FloatArray>>  // [1, 133, 384]
    val simccY = outputs[1].value as Array<Array<FloatArray>>  // [1, 133, 288]

    val keypoints = mutableListOf<Keypoint>()
    for (i in 0 until 133) {
        val x = simccX[0][i].argMax() / 384.0f
        val y = simccY[0][i].argMax() / 288.0f
        val conf = (simccX[0][i].max() + simccY[0][i].max()) / 2.0f

        keypoints.add(Keypoint(x, y, conf))
    }

    return keypoints
}

// Helper
fun FloatArray.argMax(): Int {
    var maxIdx = 0
    var maxVal = this[0]
    for (i in 1 until size) {
        if (this[i] > maxVal) {
            maxVal = this[i]
            maxIdx = i
        }
    }
    return maxIdx
}
```

---

### 2. YOLOX (옵션)

**파일명:** `yolox_int8.onnx`
**크기:** 97 MB
**위치:** `ios/TryAngleApp/Models/ONNX/yolox_int8.onnx`

**용도:**
- 사람 검출 (Person Detection)
- RTMPose 전에 사람 영역 크롭 (성능 최적화용)

**입력:**
- 형식: `int8` (양자화됨)
- Shape: `[1, 3, 416, 416]`
- 범위: -128 ~ 127

**출력:**
- Bounding boxes: `[N, 4]` (x1, y1, x2, y2)
- Confidence scores: `[N]`
- Class IDs: `[N]` (0 = person)

**사용 여부:**
- ✅ **성능 최적화가 필요하면** 사용 (사람 영역만 RTMPose에 전달)
- ❌ **단순화하려면** 생략 가능 (전체 이미지를 RTMPose에 전달)

---

## 🚀 Android에서 ONNX Runtime 설정

### Gradle 의존성 추가

```gradle
// app/build.gradle
android {
    // ...
    packagingOptions {
        pickFirst 'lib/arm64-v8a/libc++_shared.so'
        pickFirst 'lib/armeabi-v7a/libc++_shared.so'
    }
}

dependencies {
    // ONNX Runtime
    implementation 'com.microsoft.onnxruntime:onnxruntime-android:1.17.0'

    // 이미지 처리 (옵션)
    implementation 'org.tensorflow:tensorflow-lite:2.14.0'
    implementation 'org.tensorflow:tensorflow-lite-support:0.4.4'
}
```

### 모델 파일 배치

```
app/src/main/
├── assets/
│   ├── rtmpose_int8.onnx    (218MB)
│   └── yolox_int8.onnx      (97MB, 옵션)
└── java/
    └── com/yourapp/
        └── ml/
            ├── RTMPoseRunner.kt
            └── YOLOXDetector.kt
```

### 모델 로드

```kotlin
class RTMPoseRunner(context: Context) {
    private val env = OrtEnvironment.getEnvironment()
    private val session: OrtSession

    init {
        // assets에서 모델 로드
        val modelBytes = context.assets.open("rtmpose_int8.onnx").readBytes()
        val sessionOptions = OrtSession.SessionOptions()
        sessionOptions.setIntraOpNumThreads(4)  // CPU 코어 수

        session = env.createSession(modelBytes, sessionOptions)
    }

    fun detectPose(bitmap: Bitmap): List<Keypoint> {
        // (위의 코드 참고)
    }

    fun close() {
        session.close()
    }
}
```

---

## 📊 키포인트 인덱스 맵

### Body Keypoints (0-16)
```
0: Nose (코)
1-2: Left/Right Eye (눈)
3-4: Left/Right Ear (귀)
5-6: Left/Right Shoulder (어깨)
7-8: Left/Right Elbow (팔꿈치)
9-10: Left/Right Wrist (손목)
11-12: Left/Right Hip (엉덩이)
13-14: Left/Right Knee (무릎)
15-16: Left/Right Ankle (발목)
```

### Feet Keypoints (17-22)
```
17-19: Left Foot (왼발 발가락 3개)
20-22: Right Foot (오른발 발가락 3개)
```

### Face Keypoints (23-90)
68개 얼굴 랜드마크 (눈썹, 눈, 코, 입, 윤곽)

### Hand Keypoints (91-132)
```
91-111: Left Hand (왼손 21개 관절)
112-132: Right Hand (오른손 21개 관절)
```

**손 관절 구조:**
```
손목(0) → 엄지(1-4) → 검지(5-8) → 중지(9-12) → 약지(13-16) → 새끼(17-20)
```

---

## 🎯 샷 타입별 사용 키포인트

| 샷 타입 | 사용 키포인트 | 인덱스 |
|---------|--------------|--------|
| Extreme Close Up | 얼굴 + 손 | 0-4, 23-132 |
| Close Up | 머리 + 어깨 + 얼굴 + 손 | 0-6, 23-132 |
| Medium Shot | 상반신 + 얼굴 + 손 | 0-12, 23-132 |
| American Shot | 무릎 위 + 얼굴 + 손 | 0-14, 23-132 |
| Full Shot | 전신 | 0-132 (전부) |

**이유:**
- 상반신 샷에서 하반신 키포인트는 보이지 않으므로 제외
- 손 제스처가 중요하므로 손 키포인트는 항상 포함
- 얼굴 방향 분석을 위해 얼굴 키포인트 포함

---

## ⚡ 성능 최적화 팁

### 1. 모델 양자화
- 이미 `int8` 양자화 적용됨
- 원본 모델 대비 **4배 작고 2~3배 빠름**

### 2. CPU 최적화
```kotlin
val sessionOptions = OrtSession.SessionOptions()
sessionOptions.setIntraOpNumThreads(4)  // CPU 코어 수만큼
sessionOptions.setInterOpNumThreads(1)
sessionOptions.setExecutionMode(OrtSession.SessionOptions.ExecutionMode.SEQUENTIAL)
```

### 3. GPU 가속 (옵션)
```kotlin
// NNAPI (Android Neural Networks API)
sessionOptions.addNnapi()

// 또는 GPU Delegate (TensorFlow Lite와 호환)
// 추가 의존성 필요
```

### 4. 이미지 리사이즈 최적화
```kotlin
// Bitmap.createScaledBitmap() 대신
val matrix = Matrix()
matrix.postScale(384f / bitmap.width, 288f / bitmap.height)
val resized = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
```

### 5. 프레임 스킵
```kotlin
// 30fps → 10fps (3프레임마다 1번 분석)
var frameCount = 0
fun onCameraFrame(bitmap: Bitmap) {
    if (frameCount++ % 3 == 0) {
        analyzeFrame(bitmap)
    }
}
```

---

## 🐛 트러블슈팅

### Q1: "Model file too large" 오류
**A:** APK 크기 제한. 해결 방법:
1. Android App Bundle (AAB) 사용
2. 모델을 서버에서 다운로드
3. 더 작은 모델 사용 (yolox 제외)

### Q2: "Out of memory" 오류
**A:** 메모리 부족. 해결 방법:
```kotlin
// 추론 후 명시적으로 해제
inputTensor.close()
outputs.forEach { it.value.close() }

// 또는 use 블록 사용
inputTensor.use { tensor ->
    session.run(mapOf("input" to tensor)).use { outputs ->
        // 처리
    }
}
```

### Q3: "Inference too slow" (추론이 너무 느림)
**A:**
1. CPU 스레드 수 증가: `setIntraOpNumThreads(4)`
2. 이미지 크기 축소: 288×384 → 192×256
3. 프레임 스킵 적용 (위 참고)
4. NNAPI 사용

### Q4: 키포인트 좌표가 이상함
**A:** 좌표 정규화 확인:
```kotlin
// 올바른 정규화
val x = xIndex / 384.0f  // 0.0 ~ 1.0
val y = yIndex / 288.0f  // 0.0 ~ 1.0

// 화면 좌표로 변환
val screenX = x * screenWidth
val screenY = y * screenHeight
```

---

## 📚 참고 자료

- **ONNX Runtime Android**: https://onnxruntime.ai/docs/get-started/with-android.html
- **RTMPose 논문**: https://arxiv.org/abs/2303.07399
- **iOS 구현**: `ios/TryAngleApp/Services/Analysis/RTMPoseRunner.swift`

---

**최종 업데이트:** 2025-11-27
