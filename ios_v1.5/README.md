# 📸 TryAngle iOS v1.5 - 실시간 사진 구도 가이드 시스템

## 🎯 프로젝트 개요

TryAngle은 **AI 기반 실시간 사진 구도 가이드 애플리케이션**입니다. 사용자가 원하는 레퍼런스 사진을 업로드하면, 실시간 카메라 뷰를 분석하여 동일한 구도를 재현할 수 있도록 구체적인 피드백을 제공합니다.

### 주요 기능
- **5단계 Gate 시스템**: 비율, 샷타입, 여백, 압축감, 포즈를 체계적으로 평가
- **실시간 분석**: 50ms 간격으로 프레임 분석 및 즉각적 피드백
- **통합 피드백**: 하나의 동작으로 여러 문제를 동시에 해결하는 스마트 가이드
- **안정화 시스템**: 깜빡임 방지 및 Temporal Lock으로 완벽한 순간 포착

---

## 🏗️ 시스템 아키텍처

### 전체 흐름도
```
┌─────────────────┐
│ 레퍼런스 업로드  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│   레퍼런스 분석 (1회)            │
│  - RTMPose (133 키포인트)        │
│  - Depth Anything (압축감)       │
│  - YOLOX (정밀 BBox)             │
│  - MarginAnalyzer (여백)         │
│  - FocalLengthEstimator (초점거리)│
└────────┬────────────────────────┘
         │ 캐싱
         ▼
┌─────────────────────────────────┐
│   실시간 분석 (50ms마다)         │
│  - RTMPose (현재 포즈)           │
│  - Depth Anything (프레임 스킵)  │
│  - YOLOX (프레임 스킵)           │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Gate System 평가              │
│  Gate 0: 비율 (절대 우선)       │
│  Gate 1: 프레이밍 (샷타입)      │
│  Gate 2: 위치/여백              │
│  Gate 3: 압축감 (초점거리)      │
│  Gate 4: 포즈                   │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   UnifiedFeedbackGenerator      │
│  "한 걸음 앞으로"                │
│  "줌인 후 두 걸음 뒤로"          │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   UI 업데이트                   │
│  - 피드백 표시                  │
│  - Gate 점수 시각화             │
│  - Temporal Lock 진행바         │
└─────────────────────────────────┘
```

---

## 🤖 AI 모델 구성

### 1. RTMPose (포즈 추정)

#### 모델 구조
- **Stage 1**: YOLOX - 인물 검출 (BBox 추출)
- **Stage 2**: RTMPose - 133개 키포인트 추정

#### 키포인트 구성
| 그룹 | 범위 | 개수 | 설명 |
|------|------|------|------|
| Body | 0-16 | 17개 | 코, 눈, 어깨, 팔꿈치, 손목, 엉덩이, 무릎, 발목 |
| Feet | 17-22 | 6개 | 발가락, 뒤꿈치 |
| Face | 23-90 | 68개 | 얼굴 윤곽, 눈썹, 코, 눈, 입 |
| Left Hand | 91-111 | 21개 | 손목 + 손가락 관절 (엄지~소지) |
| Right Hand | 112-132 | 21개 | 손목 + 손가락 관절 (엄지~소지) |

#### 동작 원리
```swift
// 1. YOLOX로 인물 BBox 검출
640x640 입력 → YOLOX → BBox (x1, y1, x2, y2, confidence)

// 2. BBox 영역 크롭 (40% 패딩 추가로 손 포함)
croppedImage = cropWithPadding(image, bbox, padding: 0.4)

// 3. RTMPose로 키포인트 추정
192x256 입력 → RTMPose → SimCC 출력 (x: 384 bins, y: 512 bins)

// 4. SimCC에서 좌표 추출
for each keypoint:
    x_coord = argmax(simcc_x[i]) / 384 * 192
    y_coord = argmax(simcc_y[i]) / 512 * 256
    confidence = (max(simcc_x[i]) + max(simcc_y[i])) / 2
```

#### 성능 최적화
- **CoreML GPU 가속**: CPU 대비 3-5배 고속화
- **Accelerate 벡터화**: 이미지 전처리 병렬화 (40% 속도 향상)
- **추론 시간**: 50-100ms (iPhone 12 Pro 기준)

#### 코드 위치
- `ios_v1.5/TryAngleApp/Services/Analysis/RTMPoseRunner.swift`
- `ios_v1.5/TryAngleApp/Services/OnDevice/PersonDetector.swift`

---

### 2. Depth Anything V2 (깊이 추정)

#### 모델 정보
- **모델명**: DepthAnythingV2SmallF16 (Apple CoreML 버전)
- **입력**: 518x518 RGB 이미지
- **출력**: Depth Map (Float32 PixelBuffer)

#### 압축감 계산 알고리즘
```python
# 1. 배경 깊이 (상단 1/3)
backgroundDepth = mean(depthMap[0 : height/3, :])

# 2. 전경 깊이 (하단 1/4)
foregroundDepth = mean(depthMap[3*height/4 : height, :])

# 3. 압축감 지수 (0=광각, 1=망원)
depthRange = abs(backgroundDepth - foregroundDepth)
compressionIndex = 1.0 - min(depthRange * 2, 1.0)
```

#### 압축감 → 카메라 타입 매핑
| compressionIndex | 카메라 타입 | 35mm 환산 초점거리 |
|------------------|-------------|-------------------|
| 0.0 ~ 0.3 | 광각 (Wide) | 24-35mm |
| 0.3 ~ 0.5 | 표준 (Normal) | 35-50mm |
| 0.5 ~ 0.7 | 준망원 (Semi-Tele) | 50-85mm |
| 0.7 ~ 1.0 | 망원 (Telephoto) | 85mm+ |

#### 성능 최적화
- **프레임 스킵**: Level 2 (10프레임마다 1회 실행)
- **동시 실행 방지**: `isProcessing` 플래그
- **결과 캐싱**: `lastDepthResult` 재사용
- **이미지 다운샘플링**: 518x518로 리사이즈

#### 메모리 최적화
- CIContext 싱글톤 (약 100MB 절약)
- MLMultiArray 제거 (약 4MB 절약)
- autoreleasepool로 임시 메모리 즉시 해제

#### 코드 위치
- `ios_v1.5/TryAngleApp/Services/OnDevice/DepthAnythingCoreML.swift`

---

### 3. AdaptivePoseComparator (포즈 비교)

#### 비교 알고리즘
포즈 비교는 **3가지 메트릭**을 결합합니다:

##### A. 각도 차이 (3점 각도 계산)
```swift
// 팔 각도: 어깨-팔꿈치-손목
func calculateArmAngle(shoulder: CGPoint, elbow: CGPoint, wrist: CGPoint) -> Float {
    v1 = shoulder - elbow
    v2 = wrist - elbow
    angle = acos(dot(v1, v2) / (|v1| * |v2|)) * 180/π
    return angle
}

refAngle = calculateArmAngle(ref.shoulder, ref.elbow, ref.wrist)
curAngle = calculateArmAngle(cur.shoulder, cur.elbow, cur.wrist)
```

##### B. 벡터 방향 유사도 (코사인 유사도)
```swift
// 왜 필요한가? 각도만으로는 방향 구별 불가!
// 예: 팔을 앞으로 뻗음(180°) vs 팔을 위로 뻗음(180°) → 각도 같지만 방향 다름

refVector1 = normalize(shoulder → elbow)
curVector1 = normalize(shoulder → elbow)

cosineSimilarity = dot(refVector1, curVector1)  // -1 ~ 1
normalizedSimilarity = (cosineSimilarity + 1.0) / 2.0  // 0 ~ 1

directionPenalty = max(0, (1.0 - normalizedSimilarity) * 30.0)  // 최대 30도 페널티
```

##### C. 상대 위치 비교 (Y 좌표)
```swift
// 구체적인 피드백 생성용
refWristY = referenceKeypoints[9].point.y
curWristY = currentKeypoints[9].point.y
yDiff = curWristY - refWristY

if abs(yDiff) > 0.05:  // 5% 이상 차이
    if yDiff > 0:
        feedback = "왼팔을 위로 올리세요"
    else:
        feedback = "왼팔을 아래로 내리세요"
```

#### 최종 점수 계산
```swift
totalDiff = abs(refAngle - curAngle) + directionPenalty

// 각 부위별 정확도
accuracy = max(0.0, 1.0 - totalDiff / 180.0)  // 180도 차이 = 0점

// 전체 정확도 (평균)
overallAccuracy = sum(accuracies) / count(accuracies)
```

#### 신뢰도 임계값 (적응형)
| 부위 | 임계값 | 이유 |
|------|--------|------|
| Body (0-16) | 0.5 | 엄격 (핵심 부위) |
| Face (23-90) | 0.4 | 중간 (얼굴 가려지기 쉬움) |
| Hand (91-132) | 0.3 | 관대 (손 자주 가려짐) |

#### 코드 위치
- `ios_v1.5/TryAngleApp/Services/Comparison/AdaptivePoseComparator.swift`

---

## 🚪 Gate System (5단계 평가)

### Gate 0: 비율 체크 (절대 우선)

#### 평가 기준
```swift
// 비율 허용 오차: 2%
aspectRatioTolerance = 0.02

currentRatio = imageWidth / imageHeight
referenceRatio = refWidth / refHeight

if abs(currentRatio - referenceRatio) <= aspectRatioTolerance:
    score = 1.0
    feedback = "비율이 완벽합니다"
else:
    score = 0.0
    feedback = "카메라 비율을 {reference}로 변경하세요"
```

#### 지원 비율
- 4:3 (1.33)
- 3:2 (1.50)
- 16:9 (1.78)
- 1:1 (1.00)

---

### Gate 1: 프레이밍 (샷타입 + 점유율)

#### 샷타입 자동 판별 (키포인트 기반)
```swift
func detectShotType(keypoints: [Keypoint]) -> ShotType {
    // 가시성 판단 (신뢰도 0.5 이상)
    hasAnkles = keypoints[15].confidence > 0.5 || keypoints[16].confidence > 0.5
    hasFeet = keypoints[17...22].any { $0.confidence > 0.5 }
    hasKnees = keypoints[13].confidence > 0.5 || keypoints[14].confidence > 0.5
    hasHips = keypoints[11].confidence > 0.5 || keypoints[12].confidence > 0.5
    hasElbows = keypoints[7].confidence > 0.5 || keypoints[8].confidence > 0.5
    hasShoulders = keypoints[5].confidence > 0.5 || keypoints[6].confidence > 0.5

    // 샷타입 결정 (하체부터 체크)
    if hasAnkles || hasFeet:
        return .fullShot  // 전신샷
    else if hasKnees:
        return kneesYRatio < 0.7 ? .mediumFullShot : .americanShot
    else if hasHips:
        return hasElbows ? .mediumShot : .mediumCloseUp
    else if hasElbows:
        return .mediumCloseUp
    else if hasShoulders:
        return faceKeypointCount > 50 ? .closeUp : .mediumCloseUp
    else:
        return .extremeCloseUp
}
```

#### 샷타입 분류 체계
| 샷타입 | 한국어 | 보이는 부위 | 용도 |
|--------|--------|-------------|------|
| Extreme Close-Up | 익스트림 클로즈업 | 얼굴 일부 | 눈, 입 강조 |
| Close-Up | 클로즈업 | 얼굴 전체 | 표정 중심 |
| Medium Close-Up | 바스트샷 | 머리~가슴 | 인터뷰, 프로필 |
| Medium Shot | 웨이스트샷 | 머리~허리 | 대화, 상반신 |
| American Shot | 니샷 | 머리~무릎 | 액션, 제스처 |
| Medium Full Shot | 7부샷 | 머리~종아리 | 패션, 전신 |
| Full Shot | 전신샷 | 머리~발 | 전신 포즈 |
| Long Shot | 롱샷 | 전신 + 배경 | 환경 포함 |

#### 점수 계산
```swift
// 샷타입 거리 (0~7 단계 차이)
shotTypeDist = currentShotType.distance(to: referenceShotType)

if shotTypeDist == 0:
    score = 1.0  // 완벽 일치
else if shotTypeDist == 1:
    score = 0.85  // 인접 샷타입 (예: 웨이스트 vs 니샷)
else:
    score = max(0.3, 1.0 - shotTypeDist * 0.4)  // 거리 1당 0.4 감점
```

#### 프레임 잘림 감지
```swift
// BBox가 프레임 경계에 닿았는지 확인 (2% 이내)
edgeThreshold = 0.02

isAtTop = bbox.minY < edgeThreshold
isAtBottom = bbox.maxY > (1.0 - edgeThreshold)
isAtLeft = bbox.minX < edgeThreshold
isAtRight = bbox.maxX > (1.0 - edgeThreshold)

edgeCount = [isAtTop, isAtBottom, isAtLeft, isAtRight].count(where: { $0 })

if edgeCount >= 2:
    score -= 0.2

    // 어떤 부위가 잘렸는지 판단
    croppedParts = detectCroppedBodyParts(bbox, keypoints)
    feedback = "너무 가까워요! {croppedParts}이 잘렸어요. 뒤로 물러나세요"
```

---

### Gate 2: 위치/구도 (여백 + 정렬)

#### 평가 우선순위
1. **키포인트 기반 정렬** (우선) - Python v6 improved_margin_analyzer.py 이식
2. **BBox 여백 분석** (Fallback)

#### A. 키포인트 기반 정렬 (BodyStructure)

##### 1) 동적 중심점 추출
```swift
struct BodyStructure {
    let centroid: CGPoint          // 핵심 키포인트들의 평균
    let topAnchorY: CGFloat        // 머리 상단
    let spanY: CGFloat             // 머리~최하단 범위
    let lowestTier: Int            // 0:어깨, 1:엉덩이, 2:무릎, 3:발목
}

// 중심점 계산 (코, 눈, 어깨, 엉덩이 평균)
coreKeypoints = [nose, leftEye, rightEye, leftShoulder, rightShoulder, leftHip, rightHip]
centroid = mean(coreKeypoints.filter { $0.confidence > 0.5 })

// 머리 상단 (코, 눈, 귀 중 가장 높은 점)
topAnchorY = min([nose.y, leftEye.y, rightEye.y, leftEar.y, rightEar.y])

// 신체 범위 (머리~최하단)
lowestVisibleY = max([ankle.y, knee.y, hip.y, shoulder.y])  // 가장 낮은 가시 부위
spanY = lowestVisibleY - topAnchorY
```

##### 2) 좌우 정렬 (Centroid X)
```swift
diffX = currStruct.centroid.x - refStruct.centroid.x

if abs(diffX) > 0.05:  // 5% 이상 차이
    percent = abs(diffX) * 100
    steps = toSteps(percent)  // "반 걸음", "한 걸음", etc.

    if diffX > 0:  // 현재가 오른쪽에 치우침
        feedback = "왼쪽으로 {steps} 이동 ({percent}%)"
    else:
        feedback = "오른쪽으로 {steps} 이동 ({percent}%)"
```

##### 3) 상하 정렬 (Top Anchor Y)
```swift
diffY = currStruct.topAnchorY - refStruct.topAnchorY

if abs(diffY) > 0.05:
    percent = abs(diffY) * 100
    angle = toTiltAngle(percent)  // 2°, 5°, 8°, 10°, 15°

    if diffY > 0:  // 현재가 아래에 치우침 (상단 여백 많음)
        feedback = "카메라를 {angle}° 아래로 틸트"
    else:
        feedback = "카메라를 {angle}° 위로 틸트"
```

##### 4) 거리 일치 (SpanY 비율)
```swift
scaleRatio = currStruct.spanY / refStruct.spanY
scaleDiff = abs(1.0 - scaleRatio)

if scaleDiff > 0.08:  // 8% 이상 차이
    percent = scaleDiff * 50
    steps = toSteps(percent)

    if scaleRatio > 1.0:  // 현재가 더 큼 (너무 가까움)
        feedback = "뒤로 {steps} 가세요"
    else:  // 현재가 더 작음 (너무 멀음)
        feedback = "앞으로 {steps} 다가오세요"
```

#### B. BBox 여백 분석 (Fallback)

##### 여백 계산
```swift
// 픽셀 여백
leftMargin = bbox.minX
rightMargin = imageWidth - bbox.maxX
topMargin = bbox.minY
bottomMargin = imageHeight - bbox.maxY

// 비율 여백
leftRatio = leftMargin / imageWidth
rightRatio = rightMargin / imageWidth
topRatio = topMargin / imageHeight
bottomRatio = bottomMargin / imageHeight

// 균형 점수
horizontalBalance = 1.0 - abs(leftRatio - rightRatio)
verticalBalance = 1.0 - abs(topRatio - bottomRatio * 0.5)  // 하단 2:1 비율 선호
balanceScore = (horizontalBalance + verticalBalance) / 2.0
```

##### 좌우 균형 분석
```swift
currBalance = curMargins.leftRatio - curMargins.rightRatio
refBalance = refMargins.leftRatio - refMargins.rightRatio
centerShift = currBalance - refBalance

if abs(centerShift) < 0.05:
    score = 0.95  // 완벽
else if abs(centerShift) < 0.10:
    score = 0.85  // 좋음
else if abs(centerShift) < 0.15:
    score = 0.70  // 조정 필요
else:
    score = max(0.50, 0.85 - abs(centerShift))

if abs(centerShift) > 0.10:
    percent = Int(abs(centerShift) * 100)
    steps = toSteps(percent)
    feedback = "오른쪽으로 {steps} 이동 ({percent}%)"
```

##### 상하 균형 + 틸트 분석
```swift
// 인물의 수직 위치 (0=상단, 0.5=중앙, 1=하단)
personVerticalPosition = (bbox.minY + bbox.maxY) / 2.0

currPosition = curMargins.personVerticalPosition
refPosition = refMargins.personVerticalPosition
positionDiff = currPosition - refPosition

if abs(positionDiff) > 0.10:
    tiltAngle = toTiltAngle(percent: abs(positionDiff) * 100)

    if positionDiff > 0:  // 현재가 더 아래 (상단 여백 많음)
        if curMargins.isHighAngle:  // 하이앵글 감지
            feedback = "카메라를 낮추고 {tiltAngle}° 평행하게"
        else:
            feedback = "카메라를 {tiltAngle}° 아래로 틸트"
```

##### 하단 특별 분석
```swift
currBottom = curMargins.bottomRatio
refBottom = refMargins.bottomRatio
diff = abs(currBottom - refBottom)

if currBottom < -0.1:  // 하단 10% 이상 잘림
    feedback = "하단이 잘렸어요. 카메라를 위로 들거나 뒤로 물러나세요"
else if currBottom > refBottom + 0.15:  // 하단 여백 너무 많음
    feedback = "하단 여백이 너무 많아요. 카메라를 아래로 내리세요"
```

#### 퍼센트 → 걸음수/각도 변환
```swift
func toSteps(percent: CGFloat) -> String {
    if percent < 5: return "아주 조금"
    if percent < 10: return "반 걸음"
    if percent < 20: return "한 걸음"
    if percent < 30: return "두 걸음"
    if percent < 40: return "세 걸음"
    return "네 걸음 이상"
}

func toTiltAngle(percent: CGFloat) -> Int {
    if percent < 5: return 2
    if percent < 10: return 5
    if percent < 15: return 8
    if percent < 20: return 10
    return min(15, Int(percent * 0.5))
}
```

---

### Gate 3: 압축감 (35mm 환산 초점거리)

#### 평가 방법 우선순위
1. **EXIF 기반** (우선) - 정확도 높음
2. **Depth 기반** (Fallback) - EXIF 없을 때

#### A. EXIF 기반 초점거리 추출
```swift
// 이미지 메타데이터에서 추출
if let exifDict = imageData.exifDictionary {
    focalLengthMM = exifDict["FocalLength"]  // 예: 4.25mm (iPhone 실제 초점거리)
    focalLength35mm = exifDict["FocalLengthIn35mmFilm"]  // 예: 26mm (환산 초점거리)

    if focalLength35mm == nil {
        // 크롭 팩터로 계산
        cropFactor = estimateCropFactor(sensorSize)
        focalLength35mm = focalLengthMM * cropFactor
    }
}
```

#### B. Depth 기반 추정 (EXIF 없을 때)
```swift
compressionIndex = depthAnything.estimate(image)  // 0~1

// 압축감 → 초점거리 매핑
if compressionIndex < 0.3:
    estimatedFocal = 24mm  // 광각
else if compressionIndex < 0.5:
    estimatedFocal = 35mm  // 표준
else if compressionIndex < 0.7:
    estimatedFocal = 50mm  // 준망원
else:
    estimatedFocal = 85mm  // 망원
```

#### 평가 로직
```swift
currentMM = currentFocalLength.focalLength35mm
refMM = referenceFocalLength.focalLength35mm
diff = abs(currentMM - refMM)

// 점수 계산 (5mm 차이마다 10% 감점)
score = max(0, 1.0 - diff / 50.0)

// 10mm 이상 차이나면 피드백
if diff > 10:
    targetZoom = refMM / iPhoneBaseFocalLength  // 예: 50mm / 26mm = 1.9x

    if currentMM < refMM:  // 현재가 광각
        feedback = "뒤로 물러나서 {targetZoom}x로 줌인 (배경 압축)"
    else:  // 현재가 망원
        feedback = "앞으로 다가가서 {targetZoom}x로 줌아웃 (원근감 강조)"
```

#### 거리 일치 체크 (렌즈는 맞지만 거리가 다른 경우)
```swift
// 렌즈가 비슷해도 (diff < 10mm) 거리가 다를 수 있음!
if diff < 10:
    scaleRatio = currStruct.spanY / refStruct.spanY
    scaleDiff = abs(1.0 - scaleRatio)

    if scaleDiff > 0.15:  // 15% 이상 차이
        score = max(0.2, score - scaleDiff)
        steps = toSteps(percent: scaleDiff * 50)

        if scaleRatio > 1.0:  // 너무 가까움
            feedback = "렌즈는 비슷하지만 너무 가깝습니다. 뒤로 {steps} 물러나세요"
        else:  // 너무 멀음
            feedback = "렌즈는 비슷하지만 너무 멉니다. 앞으로 {steps} 다가가세요"
```

---

### Gate 4: 포즈

#### 평가 항목
- 왼팔 각도 (어깨-팔꿈치-손목)
- 오른팔 각도 (어깨-팔꿈치-손목)
- 왼다리 각도 (엉덩이-무릎-발목)
- 오른다리 각도 (엉덩이-무릎-발목)
- 어깨 기울기 (몸통 기울기)
- 왼손 모양 (손가락 방향)
- 오른손 모양 (손가락 방향)
- 발 위치
- 얼굴 방향

#### 각도 차이 계산 (예: 왼팔)
```swift
// 1. 각도 계산
refAngle = calculateArmAngle(ref.shoulder, ref.elbow, ref.wrist)
curAngle = calculateArmAngle(cur.shoulder, cur.elbow, cur.wrist)

// 2. 벡터 방향 유사도
refVector1 = normalize(ref.shoulder → ref.elbow)
curVector1 = normalize(cur.shoulder → cur.elbow)
directionSimilarity = cosineSimilarity(refVector1, curVector1)

// 3. 방향 페널티
directionPenalty = max(0, (1.0 - directionSimilarity) * 30.0)

// 4. 최종 차이
totalDiff = abs(refAngle - curAngle) + directionPenalty
angleDifferences["left_arm"] = totalDiff

// 5. 구체적 방향
yDiff = cur.wrist.y - ref.wrist.y
if yDiff > 0.05:
    angleDirections["left_arm"] = "왼팔을 위로 올리세요"
else if yDiff < -0.05:
    angleDirections["left_arm"] = "왼팔을 아래로 내리세요"
```

#### 포즈 정확도 → 점수 변환
```swift
angleTolerance = 15.0  // 15도 이내 허용

for (part, diff) in angleDifferences:
    accuracy = max(0.0, 1.0 - diff / 180.0)  // 180도 차이 = 0점
    totalAccuracy += accuracy

overallAccuracy = totalAccuracy / angleDifferences.count

// 점수 계산
if overallAccuracy >= 0.85:
    score = 1.0  // 완벽
else if overallAccuracy >= 0.70:
    score = 0.85  // 좋음
else:
    score = overallAccuracy
```

#### 피드백 통합 (좌우 분리 안함)
```swift
// 기존: "왼팔 조정", "오른팔 조정" (2개 피드백)
// 개선: "양팔 위치 조정" (1개 통합 피드백)

leftArmDiff = angleDifferences["left_arm"]
rightArmDiff = angleDifferences["right_arm"]

if abs(leftArmDiff) > 15 && abs(rightArmDiff) > 15:
    level = differenceLevel(max(leftArmDiff, rightArmDiff))
    feedback = "양팔 위치를 {level} 조정해주세요"
else if abs(leftArmDiff) > 15:
    feedback = "왼팔을 {level} 조정해주세요"
else if abs(rightArmDiff) > 15:
    feedback = "오른팔을 {level} 조정해주세요"
```

---

## 🔄 UnifiedFeedbackGenerator (통합 피드백)

### 핵심 아이디어
**"하나의 동작으로 여러 Gate를 동시에 해결"**

기존 문제:
- Gate 1: "앞으로 가세요" (샷타입)
- Gate 2: "왼쪽으로 이동" (여백)
- Gate 3: "줌인하세요" (압축감)
- 사용자: "셋 다 해야 하나? 순서는?" (혼란)

개선:
- "줌인 후 두 걸음 뒤로" (압축감 + 샷타입 + 여백 동시 해결)

### 압축감 기반 스마트 분기

```swift
if compressionOK:
    // Case A: 압축감 OK → 거리/위치만 조정 (줌 언급 안함!)
    return generateDistanceOnlyFeedback()
else:
    // Case B: 압축감 NG → 줌 + 거리 복합 조정
    return generateZoomAndDistanceFeedback()
```

#### Case A: 압축감 OK - 거리만 조정
```swift
// 줌 제외하고 거리/위치 동작만 계산
possibleActions = [moveForward, moveBackward, moveLeft, moveRight, tiltUp, tiltDown]

// 스마트 상관관계 분석
if shotTypeTooWide && marginTopHigh:
    recommend = tiltDown
    expectedResults = ["샷타입이 좁아집니다", "상단 여백이 줄어듭니다"]
    feedback = "카메라를 5° 아래로 틸트"

if shotTypeTooNarrow && marginBottomLow:
    recommend = moveBackward
    expectedResults = ["샷타입이 넓어집니다", "하단 잘림이 해결됩니다"]
    feedback = "두 걸음 뒤로 물러나세요"
```

#### Case B: 압축감 NG - 줌 + 거리 복합
```swift
zoomRatio = targetZoom / currentZoom  // 예: 2.0x / 1.0x = 2.0
needZoomIn = zoomRatio > 1.1  // 10% 이상 차이

// 줌 후 예상 인물 크기
curSize = 0.3  // 현재 점유율 30%
tgtSize = 0.4  // 목표 점유율 40%
predictedSize = curSize * zoomRatio  // 0.3 * 2.0 = 0.6 (60%)

if needZoomIn:
    if predictedSize > tgtSize * 1.15:  // 줌인 후 너무 커짐 (60% > 46%)
        action = zoomInThenMoveBack
        magnitude = calculateDistance(0.6 / 0.4)  // 1.5 → "두 걸음"
        feedback = "2.0x로 줌인 후, 두 걸음 뒤로 (배경 압축)"
        expectedResults = ["압축감이 맞춰집니다", "인물 크기가 조정됩니다"]
    else if predictedSize < tgtSize * 0.85:  // 줌인 후 너무 작아짐
        action = zoomInThenMoveForward
        feedback = "2.0x로 줌인 후, 한 걸음 앞으로"
    else:  // 줌인만 하면 크기도 OK
        action = zoomIn
        feedback = "2.0x로 줌인"
        expectedResults = ["압축감이 맞춰집니다", "인물 크기도 맞아집니다"]
```

### 동작 타입별 영향 Gate
| 동작 | 영향 Gate | 설명 |
|------|-----------|------|
| moveForward | 1, 2 | 샷타입 + 여백 |
| moveBackward | 1, 2 | 샷타입 + 여백 |
| moveLeft/Right | 2 | 여백만 |
| tiltUp/Down | 2 | 여백만 |
| zoomIn/Out | 1, 3 | 샷타입 + 압축감 |
| zoomInThenMoveBack | 1, 2, 3 | 모든 Gate |

### 피드백 안정화 (깜빡임 방지)

#### 문제 상황
```
0.00초: "앞으로 가세요"
0.05초: "틸트 다운"       ← 깜빡임!
0.10초: "앞으로 가세요"   ← 혼란!
0.15초: "틸트 다운"
```

#### 해결책: 히스테리시스
```swift
// 상태 추적
private var lastFeedback: UnifiedFeedback?
private var sameActionCount: Int = 0
private var consecutiveSameAction: Int = 0

// 안정화 로직
func stabilizeFeedback(_ newFeedback: UnifiedFeedback) -> UnifiedFeedback? {
    if let last = lastFeedback {
        if last.primaryAction == newFeedback.primaryAction:
            // 동일한 피드백
            sameActionCount += 1
            consecutiveSameAction += 1

            // magnitude만 다르면 갱신
            if last.magnitude != newFeedback.magnitude:
                return newFeedback

            return last  // 동일 피드백 유지
        } else {
            // 다른 피드백 감지 → 즉시 반영
            consecutiveSameAction = 0
            sameActionCount = 1
        }
    }

    lastFeedback = newFeedback
    return newFeedback
}
```

#### 결과
```
0.00초: "앞으로 가세요"
0.05초: "앞으로 가세요"   ← 안정적!
0.10초: "앞으로 가세요"
0.15초: "한 걸음 앞으로"  ← magnitude만 갱신
```

---

## ⚡ 실시간 분석 파이프라인

### 초기화 (앱 시작)
```swift
1. RTMPoseRunner 백그라운드 로딩 (약 17초)
   - ORTEnv 생성
   - YOLOX 모델 로드 (CoreML GPU 가속)
   - RTMPose 모델 로드 (CoreML GPU 가속)

2. DepthAnythingCoreML 모델 로딩
   - DepthAnythingV2SmallF16.mlmodelc
   - VNCoreMLModel 래핑

3. PersonDetector 연결
   - RTMPoseRunner 참조 설정
```

### 레퍼런스 분석 (1회)
```swift
func analyzeReference(image: UIImage) {
    // 1. 비율 감지
    aspectRatio = CameraAspectRatio.detect(imageSize)

    // 2. RTMPose 포즈 추정 (133개 키포인트)
    poseResult = rtmPoseRunner.detectPose(image)

    // 3. 샷타입 자동 판별
    shotType = ShotType.fromKeypoints(poseResult.keypoints)

    // 4. 비동기: Depth Anything 깊이 추정
    DispatchQueue.global().async {
        depthResult = depthAnything.estimateDepth(image)
        compressionIndex = depthResult.compressionIndex

        // 5. 비동기: YOLOX 정밀 BBox
        personDetector.detectPerson(ciImage) { preciseBBox in
            // 6. 여백 분석
            marginResult = marginAnalyzer.analyze(bbox: preciseBBox)

            // 7. 캐시 저장
            cachedReference = CacheManager.shared.cacheReference(
                image, bbox, margins, compressionIndex
            )
        }
    }

    // 8. 35mm 환산 초점거리 추정
    referenceFocalLength = focalLengthEstimator.estimateReferenceFocalLength(
        imageData: referenceImageData,  // EXIF 우선
        depthMap: referenceDepthMap     // Fallback
    )
}
```

### 실시간 프레임 분석 (50ms마다)
```swift
func process(buffer: CMSampleBuffer) {
    // 1. Throttling (50ms 간격)
    guard Date().since(lastAnalysisTime) >= 0.05 else { return }
    lastAnalysisTime = Date()

    // 2. 백그라운드에서 이미지 변환
    analysisQueue.async {
        cgImage = convertCMSampleBufferToCGImage(buffer)

        // 3. RTMPose 포즈 추정 (Level 1: 항상 실행)
        poseResult = rtmPoseRunner.detectPose(image)

        // 메인 스레드에서 Gate 평가
        DispatchQueue.main.async {
            processAnalysisResult(poseResult)
        }
    }
}

func processAnalysisResult(poseResult: RTMPoseResult) {
    frameCount += 1

    // Level 2: Depth Anything (동적 프레임 스킵, 보통 10프레임마다)
    if frameSkipper.shouldExecute(level: 2, frameCount: frameCount) {
        DispatchQueue.global().async {
            depthResult = depthAnything.estimateDepth(image)
            lastDepthResult = depthResult  // 캐시 업데이트
        }
    }

    // Level 3: YOLOX 정밀 BBox (동적 프레임 스킵, 보통 30프레임마다)
    if frameSkipper.shouldExecute(level: 3, frameCount: frameCount) {
        DispatchQueue.global().async {
            preciseBBox = personDetector.detectPerson(ciImage)
            lastPreciseBBox = preciseBBox  // 캐시 업데이트
        }
    }

    // 백그라운드에서 Gate 평가 (무거운 연산)
    DispatchQueue.global().async {
        // Gate System 평가
        evaluation = gateSystem.evaluate(
            currentBBox: poseResult.boundingBox,
            referenceBBox: cachedReference.bbox,
            currentKeypoints: poseResult.keypoints,
            referenceKeypoints: cachedReference.keypoints,
            currentCompressionIndex: lastDepthResult?.compressionIndex,
            referenceCompressionIndex: cachedReference.compressionIndex,
            currentFocalLength: estimateCurrentFocalLength(),
            referenceFocalLength: cachedReference.focalLength
        )

        // UnifiedFeedback 생성
        unifiedFeedback = UnifiedFeedbackGenerator.shared.generateUnifiedFeedback(
            from: evaluation,
            currentZoom: currentZoomFactor,
            targetZoom: cachedReference.focalLength.focalLength35mm / 26.0
        )

        // 히스테리시스 적용 (깜빡임 방지)
        stableFeedback = applyHysteresis(evaluation.primaryFeedback)

        // 메인 스레드로 UI 업데이트
        DispatchQueue.main.async {
            state.gateEvaluation = evaluation
            state.unifiedFeedback = unifiedFeedback
            state.instantFeedback = stableFeedback

            // Temporal Lock 상태 머신
            updateStabilityProgress()
        }
    }
}
```

### 프레임 스킵 전략 (AdaptiveFrameSkipper)
```swift
Level 1 (RTMPose): 항상 실행 (매 프레임)
Level 2 (Depth):   동적 간격 (보통 10프레임마다, ~200ms)
Level 3 (YOLOX):   동적 간격 (보통 30프레임마다, ~600ms)

// 동적 조정
if CPUUsage > 80%:
    level2Interval *= 1.5  // 15프레임마다
    level3Interval *= 1.5  // 45프레임마다
else if CPUUsage < 50%:
    level2Interval /= 1.2  // 8프레임마다
    level3Interval /= 1.2  // 25프레임마다
```

---

## 🌡️ 성능 최적화

### 1. 열화상 관리 (ThermalStateManager)
```swift
switch ProcessInfo.processInfo.thermalState {
case .nominal:        // 정상
    analysisInterval = 0.05  // 50ms
case .fair:           // 약간 뜨거움
    analysisInterval = 0.10  // 100ms
case .serious:        // 뜨거움
    analysisInterval = 0.20  // 200ms
case .critical:       // 매우 뜨거움
    analysisInterval = 0.50  // 500ms
}
```

### 2. 메모리 최적화

#### Depth Anything
```swift
// 싱글톤 패턴
static let shared = DepthAnythingCoreML(modelType: .small)

// CIContext 싱글톤 (약 100MB 절약)
private static let sharedContext = CIContext(options: [
    .useSoftwareRenderer: false,
    .cacheIntermediates: false
])

// 동시 실행 방지
private var isProcessing = false
guard !isProcessing else { return }
isProcessing = true
defer { isProcessing = false }

// MLMultiArray 제거 (약 4MB 절약)
struct V15DepthResult {
    let depthImage: UIImage?       // nil로 설정 가능
    let compressionIndex: Float    // 필수만
    let cameraType: V15CameraType
}
```

#### autoreleasepool 활용
```swift
DispatchQueue.global().async {
    autoreleasepool {
        // 임시 메모리 즉시 해제
        let result = heavyComputation()
        // autoreleasepool 종료 시 자동 메모리 해제
    }
}
```

### 3. 히스테리시스 (깜빡임 방지)

#### Gate별 히스테리시스
```swift
// 각 Gate 피드백마다 카운터 유지
private var feedbackHistory: [String: Int] = [:]
private let historyThreshold = 3  // 3번 연속 감지

func applyHysteresis(feedback: String, category: String) -> String? {
    feedbackHistory[category] = (feedbackHistory[category] ?? 0) + 1

    if feedbackHistory[category]! >= historyThreshold {
        return feedback  // 3번 연속 → 표시
    }

    return nil  // 아직 표시 안함
}
```

#### UnifiedFeedback 안정화
```swift
// 동일한 primaryAction이 연속으로 나와야 유지
if last.primaryAction == new.primaryAction:
    sameActionCount += 1
    if sameActionCount >= 3:  // 3번 연속
        return new
```

### 4. Temporal Lock (안정화 타이머)

#### State Machine
```swift
enum StabilityState {
    case idle                      // 완벽 아님
    case arming(startedAt: Date)   // 완벽 상태 유지 중
    case locked                    // 0.5초 이상 유지 성공!
}

private let lockDuration: TimeInterval = 0.5  // 0.5초

func updateStabilityProgress() {
    if evaluation.allPassed {
        switch stabilityState {
        case .idle:
            stabilityState = .arming(startedAt: Date())

        case .arming(let startedAt):
            let elapsed = Date().timeIntervalSince(startedAt)
            stabilityProgress = min(1.0, elapsed / lockDuration)

            if elapsed >= lockDuration:
                stabilityState = .locked
                triggerHapticFeedback()  // 햅틱 피드백
                playSuccessSound()       // 사운드

        case .locked:
            stabilityProgress = 1.0
        }
    } else {
        // Gate 실패 → 리셋
        stabilityState = .idle
        stabilityProgress = 0.0
    }
}
```

---

## 📊 성능 지표 (iPhone 12 Pro 기준)

| 항목 | 수치 | 설명 |
|------|------|------|
| RTMPose 추론 시간 | 50-100ms | CoreML GPU 가속 |
| Depth Anything 추론 시간 | 150-200ms | 10프레임마다 1회 |
| YOLOX 추론 시간 | 80-120ms | 30프레임마다 1회 |
| 프레임 분석 간격 | 50ms | 초당 20프레임 |
| 메모리 사용량 | ~300MB | 피크 시 |
| 배터리 소모 | 10%/시간 | 일반 촬영 앱 수준 |
| 열화상 관리 | 자동 조절 | nominal ~ critical |

---

## 🎓 주요 기술적 특징

### 1. 실시간성
- **50ms 간격 분석**: 초당 20프레임 처리
- **비동기 파이프라인**: UI 블로킹 없음
- **결과 캐싱**: 무거운 연산(Depth, YOLOX) 결과 재사용

### 2. 정밀도
- **133개 키포인트**: 얼굴, 손, 발까지 정밀 분석
- **깊이 추정**: Depth Anything으로 압축감 측정
- **EXIF 분석**: 실제 촬영 초점거리 추출

### 3. 사용성
- **통합 피드백**: "한 동작으로 여러 문제 해결"
- **구체적 가이드**: "두 걸음 앞으로", "5° 틸트"
- **안정화 시스템**: 깜빡임 방지 + Temporal Lock

### 4. 효율성
- **프레임 스킵**: 동적 간격 조정
- **열화상 관리**: CPU 과열 방지
- **메모리 최적화**: 싱글톤 + autoreleasepool

### 5. 확장성
- **모듈화 설계**: Gate별 독립 평가
- **Adaptive Difficulty**: 난이도 자동 조절
- **플러그인 구조**: 새로운 Gate 추가 용이

---

## 📁 파일 구조

```
ios_v1.5/TryAngleApp/
├── Services/
│   ├── Analysis/
│   │   └── RTMPoseRunner.swift              # RTMPose (YOLOX + 포즈 추정)
│   ├── OnDevice/
│   │   ├── DepthAnythingCoreML.swift        # Depth Anything (압축감)
│   │   ├── PersonDetector.swift             # 인물 검출 (YOLOX 재사용)
│   │   ├── GateSystem.swift                 # 5단계 Gate 평가
│   │   └── UnifiedFeedbackGenerator.swift   # 통합 피드백 생성
│   ├── Comparison/
│   │   └── AdaptivePoseComparator.swift     # 포즈 비교 (133 키포인트)
│   └── RealtimeAnalyzer.swift               # 실시간 분석 메인
├── Models/
│   ├── yolox_int8.onnx                      # YOLOX 모델 (INT8 양자화)
│   ├── rtmpose_int8.onnx                    # RTMPose 모델 (INT8 양자화)
│   └── DepthAnythingV2SmallF16.mlmodelc     # Depth Anything (CoreML)
└── README.md                                # 본 문서
```

---

## 🚀 시작하기

### 요구사항
- iOS 15.0+
- Xcode 14.0+
- iPhone 12 이상 권장 (CoreML GPU 성능)

### 모델 파일 준비
1. **RTMPose 모델** (ONNX)
   - `yolox_int8.onnx` (약 35MB)
   - `rtmpose_int8.onnx` (약 45MB)
   - INT8 양자화로 모델 크기 1/4 감소

2. **Depth Anything 모델** (CoreML)
   - 다운로드: https://huggingface.co/apple/coreml-depth-anything-v2-small
   - `DepthAnythingV2SmallF16.mlmodelc` (약 98MB)
   - 프로젝트의 `Resources/` 폴더에 추가

### 빌드 및 실행
```bash
# 1. 저장소 클론
git clone https://github.com/your-repo/TryAngle.git
cd TryAngle/ios_v1.5

# 2. Xcode에서 프로젝트 열기
open TryAngleApp.xcodeproj

# 3. 모델 파일 추가 (Build Phases > Copy Bundle Resources)
# - yolox_int8.onnx
# - rtmpose_int8.onnx
# - DepthAnythingV2SmallF16.mlmodelc

# 4. 빌드 및 실행 (Cmd+R)
```

---

## 🔬 예상 질문 (FAQ)

### Q1. RTMPose 추론이 느리면 어떻게 하나요?
**A**: CoreML GPU 가속이 활성화되지 않았을 가능성이 큽니다.
```swift
// RTMPoseRunner.swift에서 확인
let poseOptions = try ORTSessionOptions()
try poseOptions.appendCoreMLExecutionProvider()  // GPU 가속
```

### Q2. Depth Anything 없이도 작동하나요?
**A**: 네, EXIF 기반 초점거리 추출로 대체 가능합니다. Depth는 EXIF가 없을 때만 Fallback으로 사용됩니다.

### Q3. Gate 3 (압축감)가 항상 실패하는데요?
**A**: 레퍼런스 사진이 EXIF 메타데이터가 없고, Depth 추정도 부정확한 경우입니다. Gate 3를 선택적으로 비활성화할 수 있습니다:
```swift
// GateSystem.swift
let enableCompressionGate = false  // 압축감 Gate 비활성화
```

### Q4. 포즈 비교가 너무 엄격해요
**A**: Adaptive Difficulty 시스템이 5초 후 자동으로 완화됩니다. 수동으로 조정하려면:
```swift
// AdaptivePoseComparator.swift
private let confidenceThreshold: Float = 0.4  // 0.5 → 0.4 (더 관대)
```

### Q5. 배터리 소모가 큰데요?
**A**: 열화상 관리와 프레임 스킵 설정을 확인하세요:
```swift
// RealtimeAnalyzer.swift
private let analysisInterval: TimeInterval = 0.10  // 50ms → 100ms (더 느리게)
```

---

## 📝 라이선스

본 프로젝트는 [MIT License](LICENSE)를 따릅니다.

---

## 👥 기여자

- **개발자**: [Your Name]
- **지도 교수**: [Professor Name]
- **프로젝트 기간**: 2024.09 - 2025.01

---

## 🙏 감사의 말

본 프로젝트는 다음 오픈소스를 활용했습니다:
- **RTMPose**: [MMPose](https://github.com/open-mmlab/mmpose)
- **Depth Anything V2**: [Apple CoreML](https://huggingface.co/apple/coreml-depth-anything-v2-small)
- **ONNX Runtime**: [Microsoft](https://onnxruntime.ai/)

---

**마지막 업데이트**: 2025-12-11
