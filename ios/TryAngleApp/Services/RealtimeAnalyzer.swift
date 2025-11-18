import Foundation
import Vision
import UIKit
import CoreImage
import Combine

// MARK: - 실시간 분석을 위한 데이터 구조
struct FrameAnalysis {
    let faceRect: CGRect?                           // 얼굴 위치 (정규화된 좌표)
    let bodyRect: CGRect?                           // 전신 추정 영역
    let brightness: Float                           // 평균 밝기
    let tiltAngle: Float                            // 기울기 각도
    let faceYaw: Float?                             // 얼굴 좌우 회전 (정면=0)
    let facePitch: Float?                           // 얼굴 상하 각도
    let cameraAngle: CameraAngle                    // 카메라 각도
    let poseKeypoints: [(point: CGPoint, confidence: Float)]?  // 신뢰도 포함 키포인트
    let compositionType: CompositionType?           // 구도 타입
    let faceObservation: VNFaceObservation?         // 얼굴 관찰 결과
    let gaze: GazeResult?                           // 🆕 시선 추적 결과
    let depth: DepthResult?                         // 🆕 깊이 추정 결과
    let aspectRatio: CameraAspectRatio              // 🆕 카메라 비율
    let imagePadding: ImagePadding?                 // 🆕 여백 정보
    let imageOrientation: ImageOrientation          // 🆕 이미지 방향 (세로/가로)
}

// 🆕 이미지 여백 정보
struct ImagePadding {
    let top: CGFloat        // 상단 여백 (0.0 ~ 1.0)
    let bottom: CGFloat     // 하단 여백
    let left: CGFloat       // 좌측 여백
    let right: CGFloat      // 우측 여백

    var total: CGFloat {
        return top + bottom + left + right
    }

    var hasExcessivePadding: Bool {
        // 어느 한 쪽이 15% 이상 여백이면 과도함
        return top > 0.15 || bottom > 0.15 || left > 0.15 || right > 0.15
    }
}

// MARK: - 실시간 피드백 생성기
class RealtimeAnalyzer: ObservableObject {
    @Published var instantFeedback: [FeedbackItem] = []
    @Published var isPerfect: Bool = false  // 완벽한 상태 감지
    @Published var perfectScore: Double = 0.0  // 완성도 점수 (0~1)
    @Published var categoryStatuses: [CategoryStatus] = []  // 🆕 카테고리별 상태
    @Published var completedFeedbacks: [CompletedFeedback] = []  // 🆕 완료된 피드백들

    private var referenceAnalysis: FrameAnalysis?
    private var lastAnalysisTime = Date()
    private let analysisInterval: TimeInterval = 0.1  // 100ms마다 분석

    // 히스테리시스를 위한 상태 추적
    private var feedbackHistory: [String: Int] = [:]  // 카테고리별 연속 감지 횟수
    private let historyThreshold = 10  // 🔄 10번 연속 감지되어야 표시 (약 1초)
    private var perfectFrameCount = 0  // 완벽한 프레임 연속 횟수
    private let perfectThreshold = 10  // 10프레임(약 1초) 연속 완벽해야 감지

    // 🆕 고정 피드백 (한 번 표시되면 해결될 때까지 유지)
    private var stickyFeedbacks: [String: FeedbackItem] = [:]  // 카테고리별 고정 피드백

    // 🆕 이전 프레임의 피드백 (완료 감지용)
    private var previousFeedbackIds = Set<String>()
    // 🆕 완료 감지를 위한 히스테리시스
    private var disappearedFeedbackHistory: [String: Int] = [:]  // 사라진 피드백의 연속 횟수
    private let disappearedThreshold = 5  // 5번 연속 사라져야 완료로 판단

    // 🆕 고정 피드백 카테고리 (포즈 관련은 계속 표시)
    // pose_missing_parts는 이제 레퍼런스 기반으로 제대로 감지되므로 sticky 처리
    private let stickyCategories: Set<String> = [
        "pose_left_arm",
        "pose_right_arm",
        "pose_left_leg",
        "pose_right_leg",
        "pose_missing_parts"
    ]

    // 🆕 V1 분석기들
    private let visionAnalyzer = VisionAnalyzer()
    private let compositionAnalyzer = CompositionAnalyzer()
    private let cameraAngleDetector = CameraAngleDetector()
    private let gazeTracker = GazeTracker()
    private let depthEstimator = DepthEstimator()
    private let poseComparator = AdaptivePoseComparator()
    private let gapAnalyzer = GapAnalyzer()
    private let feedbackGenerator = FeedbackGenerator()
    private let framingAnalyzer = FramingAnalyzer()  // 🆕 프레이밍 분석기 추가

    // Vision 요청 캐싱
    private lazy var faceDetectionRequest: VNDetectFaceLandmarksRequest = {
        let request = VNDetectFaceLandmarksRequest()
        request.revision = VNDetectFaceLandmarksRequestRevision3
        return request
    }()

    private lazy var poseDetectionRequest: VNDetectHumanBodyPoseRequest = {
        let request = VNDetectHumanBodyPoseRequest()
        return request
    }()

    // MARK: - Helper Methods

    /// 여백 계산
    private func calculatePadding(bodyRect: CGRect?, imageSize: CGSize) -> ImagePadding? {
        guard let body = bodyRect else { return nil }

        let top = body.minY
        let bottom = 1.0 - body.maxY
        let left = body.minX
        let right = 1.0 - body.maxX

        return ImagePadding(
            top: top,
            bottom: bottom,
            left: left,
            right: right
        )
    }

    // MARK: - 레퍼런스 이미지 분석
    func analyzeReference(_ image: UIImage) {
        guard let cgImage = image.cgImage else { return }

        // 🆕 이미지 방향 감지 (세로/가로)
        let imageOrientation = ImageOrientation.detect(from: image)

        // 🆕 VisionAnalyzer로 얼굴+포즈 동시 분석
        let (faceResult, poseResult) = visionAnalyzer.analyzeFaceAndPose(from: image)

        let faceRect = faceResult?.faceRect
        let faceYaw = faceResult?.yaw
        let facePitch = faceResult?.pitch
        let poseKeypoints = poseResult?.keypoints

        // 밝기 계산
        let brightness = visionAnalyzer.calculateBrightness(from: cgImage)

        // 🆕 더치 틸트 감지
        let tiltAngle = cameraAngleDetector.detectDutchTilt(faceObservation: faceResult?.observation) ?? 0.0

        // 전신 영역 추정
        let bodyRect = visionAnalyzer.estimateBodyRect(from: faceRect)

        // 카메라 앵글 감지
        let cameraAngle = cameraAngleDetector.detectCameraAngle(
            faceRect: faceRect,
            facePitch: facePitch,
            faceObservation: faceResult?.observation
        )

        // 구도 타입 분류
        var compositionType: CompositionType? = nil
        if let faceRect = faceRect {
            let subjectPosition = CGPoint(x: faceRect.midX, y: faceRect.midY)
            compositionType = compositionAnalyzer.classifyComposition(subjectPosition: subjectPosition)
        }

        // 🆕 시선 추적
        var gaze: GazeResult? = nil
        if let faceObservation = faceResult?.observation {
            gaze = gazeTracker.trackGaze(from: faceObservation)
        }

        // 🆕 깊이 추정
        var depth: DepthResult? = nil
        if let faceRect = faceRect {
            depth = depthEstimator.estimateDistance(
                faceRect: faceRect,
                imageWidth: cgImage.width,
                zoomFactor: 1.0  // TODO: CameraManager에서 실제 줌 값 가져오기
            )
        }

        // 🆕 비율 감지
        let imageSize = CGSize(width: cgImage.width, height: cgImage.height)
        let aspectRatio = CameraAspectRatio.detect(from: imageSize)

        // 🆕 여백 계산
        let padding = calculatePadding(bodyRect: bodyRect, imageSize: imageSize)

        referenceAnalysis = FrameAnalysis(
            faceRect: faceRect,
            bodyRect: bodyRect,
            brightness: brightness,
            tiltAngle: tiltAngle,
            faceYaw: faceYaw,
            facePitch: facePitch,
            cameraAngle: cameraAngle,
            poseKeypoints: poseKeypoints,
            compositionType: compositionType,
            faceObservation: faceResult?.observation,
            gaze: gaze,
            depth: depth,
            aspectRatio: aspectRatio,
            imagePadding: padding,
            imageOrientation: imageOrientation
        )

        print("📸 레퍼런스 분석 완료:")
        print("   - 이미지 방향: \(imageOrientation.description)")
        print("   - 얼굴: \(faceRect != nil ? "감지됨" : "없음")")
        print("   - 얼굴 각도: yaw=\(faceYaw ?? 0), pitch=\(facePitch ?? 0)")
        print("   - 카메라 앵글: \(cameraAngle.description)")
        print("   - 구도: \(compositionType?.description ?? "알 수 없음")")
        print("   - 시선: \(gaze?.direction.description ?? "알 수 없음")")
        print("   - 거리: \(depth?.distance.map { String(format: "%.2fm", $0) } ?? "알 수 없음")")
        print("   - 포즈 키포인트: \(poseKeypoints?.count ?? 0)개")
        print("   - 밝기: \(brightness)")
        print("   - 기울기: \(tiltAngle)도")
    }

    // MARK: - 실시간 프레임 분석
    func analyzeFrame(_ image: UIImage) {
        // 너무 자주 분석하지 않도록 제한
        guard Date().timeIntervalSince(lastAnalysisTime) >= analysisInterval else { return }

        // 레퍼런스가 없으면 분석하지 않음
        guard let reference = referenceAnalysis else {
            DispatchQueue.main.async {
                self.instantFeedback = []
                self.perfectScore = 0.0
                self.isPerfect = false
            }
            return
        }

        guard let cgImage = image.cgImage else { return }
        lastAnalysisTime = Date()

        // 🆕 VisionAnalyzer로 분석
        let (faceResult, poseResult) = visionAnalyzer.analyzeFaceAndPose(from: image)

        // 얼굴이 감지되지 않으면 완성도 0으로 설정
        guard faceResult != nil else {
            DispatchQueue.main.async {
                self.instantFeedback = [FeedbackItem(
                    priority: 1,
                    icon: "👤",
                    message: "얼굴을 화면에 보여주세요",
                    category: "no_face",
                    currentValue: nil,
                    targetValue: nil,
                    tolerance: nil,
                    unit: nil
                )]
                self.perfectScore = 0.0
                self.isPerfect = false
            }
            return
        }

        // 밝기 및 기울기
        let brightness = visionAnalyzer.calculateBrightness(from: cgImage)
        let tilt = cameraAngleDetector.detectDutchTilt(faceObservation: faceResult?.observation) ?? 0.0

        // 전신 영역
        let bodyRect = visionAnalyzer.estimateBodyRect(from: faceResult?.faceRect)

        // 카메라 앵글
        let cameraAngle = cameraAngleDetector.detectCameraAngle(
            faceRect: faceResult?.faceRect,
            facePitch: faceResult?.pitch,
            faceObservation: faceResult?.observation
        )

        // 구도
        var compositionType: CompositionType? = nil
        if let faceRect = faceResult?.faceRect {
            let subjectPosition = CGPoint(x: faceRect.midX, y: faceRect.midY)
            compositionType = compositionAnalyzer.classifyComposition(subjectPosition: subjectPosition)
        }

        // 시선
        var gaze: GazeResult? = nil
        if let faceObservation = faceResult?.observation {
            gaze = gazeTracker.trackGaze(from: faceObservation)
        }

        // 깊이
        var depth: DepthResult? = nil
        if let faceRect = faceResult?.faceRect {
            depth = depthEstimator.estimateDistance(
                faceRect: faceRect,
                imageWidth: cgImage.width,
                zoomFactor: 1.0  // TODO: 실제 줌 값
            )
        }

        // 🆕 비율 감지 (현재 카메라)
        let currentImageSize = CGSize(width: cgImage.width, height: cgImage.height)
        let currentAspectRatio = CameraAspectRatio.detect(from: currentImageSize)

        // 🆕 여백 계산
        let currentPadding = calculatePadding(bodyRect: bodyRect, imageSize: currentImageSize)

        // 🆕 현재 프레임 방향 감지
        let currentOrientation = ImageOrientation.detect(from: image)

        // 🆕 프레이밍 분석 추가 (최우선)
        let currentFrame = FrameAnalysis(
            faceRect: faceResult?.faceRect,
            bodyRect: bodyRect,
            brightness: brightness,
            tiltAngle: tilt,
            faceYaw: faceResult?.yaw,
            facePitch: faceResult?.pitch,
            cameraAngle: cameraAngle,
            poseKeypoints: poseResult?.keypoints,
            compositionType: compositionType,
            faceObservation: faceResult?.observation,
            gaze: gaze,
            depth: depth,
            aspectRatio: currentAspectRatio,
            imagePadding: currentPadding,
            imageOrientation: currentOrientation
        )

        // 🆕 방향 불일치 체크 (최최우선)
        var orientationMismatchFeedback: FeedbackItem? = nil
        if reference.imageOrientation != currentOrientation {
            let targetOrientation = reference.imageOrientation.description
            orientationMismatchFeedback = FeedbackItem(
                priority: -1,  // 최고 우선순위
                icon: "📱",
                message: "핸드폰을 \(targetOrientation)로 돌려주세요",
                category: "orientation_mismatch",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        let framingResult = framingAnalyzer.analyzeFraming(
            reference: reference,
            current: currentFrame,
            currentAspectRatio: currentAspectRatio
        )

        // 🆕 GapAnalyzer로 차이 계산
        let gaps = gapAnalyzer.analyzeGaps(
            reference: reference,
            current: (
                face: faceResult,
                pose: poseResult,
                bodyRect: bodyRect,
                brightness: brightness,
                tilt: tilt,
                cameraAngle: cameraAngle,
                compositionType: compositionType,
                gaze: gaze,
                depth: depth,
                aspectRatio: currentAspectRatio,
                padding: currentPadding
            )
        )

        // 🆕 FeedbackGenerator로 피드백 생성
        var feedbacks = feedbackGenerator.generateFeedback(
            from: gaps,
            reference: reference,
            current: (
                face: faceResult,
                pose: poseResult,
                bodyRect: bodyRect,
                brightness: brightness,
                tilt: tilt,
                cameraAngle: cameraAngle,
                compositionType: compositionType,
                gaze: gaze,
                depth: depth
            )
        )

        // 프레이밍 피드백이 있으면 최우선으로 추가
        if let framing = framingResult.feedback {
            feedbacks.insert(FeedbackItem(
                priority: 0,  // 최고 우선순위
                icon: "📐",
                message: framing,
                category: "framing",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            ), at: 0)
        }

        // 히스테리시스 적용: 연속으로 감지된 피드백만 표시
        var stableFeedback: [FeedbackItem] = []
        var currentCategories = Set<String>()

        // 🆕 방향 불일치는 히스테리시스 없이 즉시 표시 (최고 우선순위)
        if let orientationFeedback = orientationMismatchFeedback {
            stableFeedback.append(orientationFeedback)
            currentCategories.insert(orientationFeedback.category)
        }

        for fb in feedbacks {
            currentCategories.insert(fb.category)
            feedbackHistory[fb.category, default: 0] += 1

            // 히스테리시스 임계값 넘으면 표시
            if feedbackHistory[fb.category]! >= historyThreshold {
                stableFeedback.append(fb)

                // 🆕 고정 카테고리면 저장 (한 번 뜨면 해결될 때까지 유지)
                if stickyCategories.contains(fb.category) {
                    stickyFeedbacks[fb.category] = fb
                }
            }
        }

        // 🆕 고정 피드백 추가 (현재 감지되지 않아도 계속 표시)
        for (category, stickyFb) in stickyFeedbacks {
            // 이미 stableFeedback에 있으면 스킵
            if !stableFeedback.contains(where: { $0.category == category }) {
                stableFeedback.append(stickyFb)
            }
        }

        // 사라진 카테고리는 히스토리 초기화
        for (category, _) in feedbackHistory {
            if !currentCategories.contains(category) {
                feedbackHistory[category] = 0

                // 🆕 고정 피드백도 제거 (완전히 해결됨)
                if stickyCategories.contains(category) {
                    // 5번 연속 사라져야 제거
                    disappearedFeedbackHistory[category, default: 0] += 1
                    if disappearedFeedbackHistory[category]! >= disappearedThreshold {
                        stickyFeedbacks.removeValue(forKey: category)
                        disappearedFeedbackHistory[category] = 0
                    }
                }
            } else {
                // 다시 나타나면 disappear 히스토리 초기화
                disappearedFeedbackHistory[category] = 0
            }
        }

        // 완벽한 상태 감지 (GapAnalyzer 사용)
        let score = gapAnalyzer.calculateCompletionScore(gaps: gaps)
        let isCurrentlyPerfect = stableFeedback.isEmpty && score > 0.95

        if isCurrentlyPerfect {
            perfectFrameCount += 1
        } else {
            perfectFrameCount = 0
        }

        // 🆕 완료된 피드백 감지 (히스테리시스 적용)
        let currentFeedbackIds = Set(stableFeedback.map { $0.id })
        let disappeared = previousFeedbackIds.subtracting(currentFeedbackIds)

        // 사라진 피드백의 연속 횟수 추적
        for disappearedId in disappeared {
            disappearedFeedbackHistory[disappearedId, default: 0] += 1

            // 5번 연속 사라지면 완료로 판단
            if disappearedFeedbackHistory[disappearedId]! >= disappearedThreshold {
                if let completedItem = self.instantFeedback.first(where: { $0.id == disappearedId }) {
                    let completed = CompletedFeedback(item: completedItem, completedAt: Date())
                    DispatchQueue.main.async {
                        self.completedFeedbacks.append(completed)
                    }
                }
                // 완료 처리 후 히스토리 초기화
                disappearedFeedbackHistory[disappearedId] = 0
            }
        }

        // 다시 나타난 피드백은 히스토리 초기화
        for (feedbackId, _) in disappearedFeedbackHistory {
            if currentFeedbackIds.contains(feedbackId) {
                disappearedFeedbackHistory[feedbackId] = 0
            }
        }

        // 2초 지난 완료 피드백 제거
        DispatchQueue.main.async {
            self.completedFeedbacks.removeAll { !$0.shouldDisplay }
        }

        // 이전 피드백 업데이트
        previousFeedbackIds = currentFeedbackIds

        // 🆕 카테고리별 상태 계산
        let categoryStatuses = calculateCategoryStatuses(from: stableFeedback)

        // 즉시 피드백 업데이트
        DispatchQueue.main.async {
            self.instantFeedback = stableFeedback
            self.perfectScore = score
            self.isPerfect = self.perfectFrameCount >= self.perfectThreshold
            self.categoryStatuses = categoryStatuses
        }
    }

    // MARK: - Category Status Calculation

    /// 카테고리별 상태 계산
    private func calculateCategoryStatuses(from feedbacks: [FeedbackItem]) -> [CategoryStatus] {
        // 모든 카테고리에 대해 상태 생성
        var statusMap: [FeedbackCategory: CategoryStatus] = [:]

        // 각 카테고리 초기화 (모두 만족 상태로 시작)
        for category in FeedbackCategory.allCases {
            statusMap[category] = CategoryStatus(
                category: category,
                isSatisfied: true,
                activeFeedbacks: []
            )
        }

        // 피드백이 있는 카테고리는 불만족 상태로 변경
        for feedback in feedbacks {
            if let category = FeedbackCategory.from(categoryString: feedback.category) {
                var activeFeedbacks = statusMap[category]?.activeFeedbacks ?? []
                activeFeedbacks.append(feedback)

                statusMap[category] = CategoryStatus(
                    category: category,
                    isSatisfied: false,
                    activeFeedbacks: activeFeedbacks.sorted { $0.priority < $1.priority }
                )
            }
        }

        // 우선순위 순서로 정렬하여 반환
        return Array(statusMap.values).sorted { $0.priority < $1.priority }
    }

    // 🗑️ 구식 함수들 제거됨 (새 컴포넌트로 대체)
    // - calculatePerfectScore() → GapAnalyzer.calculateCompletionScore() 사용
    // - calculateBrightness() → VisionAnalyzer.calculateBrightness() 사용
    // - calculateTilt() → CameraAngleDetector.detectDutchTilt() 사용
    // - estimateBodyRect() → VisionAnalyzer.estimateBodyRect() 사용
    // - extractPoseKeypoints() → VisionAnalyzer 내부 사용
    // - estimateCameraAngle() → CameraAngleDetector 사용
    // - comparePoseKeypoints() → AdaptivePoseComparator 사용
    // - calculateAngle() → AdaptivePoseComparator 내부 사용
}