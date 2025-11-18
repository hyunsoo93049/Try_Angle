import Foundation
import CoreGraphics

// MARK: - 피드백 생성기
class FeedbackGenerator {

    // 헬퍼 컴포넌트
    private let cameraAngleDetector = CameraAngleDetector()
    private let compositionAnalyzer = CompositionAnalyzer()
    private let gazeTracker = GazeTracker()
    private let depthEstimator = DepthEstimator()
    private let poseComparator = AdaptivePoseComparator()

    /// Gap 목록을 FeedbackItem으로 변환
    /// - Parameters:
    ///   - gaps: Gap 목록
    ///   - reference: 레퍼런스 분석
    ///   - current: 현재 분석
    /// - Returns: 피드백 아이템 목록
    func generateFeedback(
        from gaps: [Gap],
        reference: FrameAnalysis,
        current: (
            face: FaceAnalysisResult?,
            pose: PoseAnalysisResult?,
            bodyRect: CGRect?,
            brightness: Float,
            tilt: Float,
            cameraAngle: CameraAngle,
            compositionType: CompositionType?,
            gaze: GazeResult?,
            depth: DepthResult?
        )
    ) -> [FeedbackItem] {

        var feedbacks: [FeedbackItem] = []

        for gap in gaps {
            if let feedback = convertGapToFeedback(
                gap: gap,
                reference: reference,
                current: current
            ) {
                feedbacks.append(feedback)
            }
        }

        // 포즈 피드백 추가 (별도 처리)
        if let refPose = reference.poseKeypoints,
           let curPose = current.pose?.keypoints,
           refPose.count >= 17,
           curPose.count >= 17 {

            // 레퍼런스와 현재 프레임 모두 분석
            let referencePoseComparison = poseComparator.comparePoses(
                referenceKeypoints: refPose,
                currentKeypoints: refPose  // 레퍼런스 자체 분석
            )

            let currentPoseComparison = poseComparator.comparePoses(
                referenceKeypoints: refPose,
                currentKeypoints: curPose
            )

            // 레퍼런스 결과도 함께 전달
            let poseFeedbacks = poseComparator.generateFeedback(
                from: currentPoseComparison,
                referenceResult: referencePoseComparison
            )

            for (message, category) in poseFeedbacks {
                feedbacks.append(FeedbackItem(
                    priority: 1,  // 🔥 포즈가 최우선!
                    icon: "💪",
                    message: message,
                    category: category,
                    currentValue: nil,
                    targetValue: nil,
                    tolerance: nil,
                    unit: nil
                ))
            }
        }

        return feedbacks
    }

    // MARK: - Private Methods

    /// Gap을 FeedbackItem으로 변환
    private func convertGapToFeedback(
        gap: Gap,
        reference: FrameAnalysis,
        current: (
            face: FaceAnalysisResult?,
            pose: PoseAnalysisResult?,
            bodyRect: CGRect?,
            brightness: Float,
            tilt: Float,
            cameraAngle: CameraAngle,
            compositionType: CompositionType?,
            gaze: GazeResult?,
            depth: DepthResult?
        )
    ) -> FeedbackItem? {

        switch gap.type {
        case .distance:
            return generateDistanceFeedback(gap: gap, reference: reference, current: current)

        case .positionX:
            return generatePositionXFeedback(gap: gap)

        case .positionY:
            return generatePositionYFeedback(gap: gap)

        case .tilt:
            return generateTiltFeedback(gap: gap, current: current)

        case .faceYaw:
            return generateFaceYawFeedback(gap: gap)

        case .cameraAngle:
            return generateCameraAngleFeedback(gap: gap)

        case .gaze:
            return generateGazeFeedback(gap: gap)

        case .composition:
            return generateCompositionFeedback(gap: gap, reference: reference, current: current)

        case .aspectRatio:
            return generateAspectRatioFeedback(gap: gap)

        case .excessivePadding:
            return generatePaddingFeedback(gap: gap)

        default:
            return nil
        }
    }

    /// 거리 피드백 생성
    private func generateDistanceFeedback(
        gap: Gap,
        reference: FrameAnalysis,
        current: (
            face: FaceAnalysisResult?,
            pose: PoseAnalysisResult?,
            bodyRect: CGRect?,
            brightness: Float,
            tilt: Float,
            cameraAngle: CameraAngle,
            compositionType: CompositionType?,
            gaze: GazeResult?,
            depth: DepthResult?
        )
    ) -> FeedbackItem? {

        guard let refDepth = reference.depth, let curDepth = current.depth else {
            return nil
        }

        if let (message, shouldUseZoom) = depthEstimator.generateDistanceFeedback(
            reference: refDepth,
            current: curDepth
        ) {
            return FeedbackItem(
                priority: gap.priority,
                icon: shouldUseZoom ? "🔍" : "🚶",
                message: message,
                category: "distance",
                currentValue: gap.current,
                targetValue: gap.target,
                tolerance: gap.tolerance,
                unit: "m"
            )
        }

        return nil
    }

    /// X 위치 피드백
    private func generatePositionXFeedback(gap: Gap) -> FeedbackItem {
        guard let current = gap.current, let target = gap.target else {
            return FeedbackItem(
                priority: gap.priority,
                icon: "↔️",
                message: "좌우 위치를 맞춰주세요",
                category: "position_x",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        // current > target: 화면에서 오른쪽에 있음 → 왼쪽으로 이동 필요
        let direction = current > target ? "왼쪽" : "오른쪽"
        return FeedbackItem(
            priority: gap.priority,
            icon: "↔️",
            message: "\(direction)으로 서주세요",
            category: "position_x",
            currentValue: current,
            targetValue: target,
            tolerance: gap.tolerance,
            unit: "%"
        )
    }

    /// Y 위치 피드백
    private func generatePositionYFeedback(gap: Gap) -> FeedbackItem {
        guard let current = gap.current, let target = gap.target else {
            return FeedbackItem(
                priority: gap.priority,
                icon: "↕️",
                message: "상하 위치를 맞춰주세요",
                category: "position_y",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        // 🔄 카메라 움직임 기준으로 피드백 (수정됨 ✅)
        // Vision 좌표계: Y=0(아래), Y=1(위)
        // current > target: 인물이 화면 위쪽에 있음 → 카메라를 아래로 내려서 인물을 중앙으로
        // current < target: 인물이 화면 아래쪽에 있음 → 카메라를 위로 올려서 인물을 중앙으로
        let cameraDirection = current > target ? "아래로" : "위로"
        return FeedbackItem(
            priority: gap.priority,
            icon: "📷",
            message: "카메라를 \(cameraDirection) 이동하세요",
            category: "position_y",
            currentValue: current,
            targetValue: target,
            tolerance: gap.tolerance,
            unit: "%"
        )
    }

    /// 기울기 피드백
    private func generateTiltFeedback(
        gap: Gap,
        current: (
            face: FaceAnalysisResult?,
            pose: PoseAnalysisResult?,
            bodyRect: CGRect?,
            brightness: Float,
            tilt: Float,
            cameraAngle: CameraAngle,
            compositionType: CompositionType?,
            gaze: GazeResult?,
            depth: DepthResult?
        )
    ) -> FeedbackItem {
        guard let current = gap.current, let target = gap.target else {
            return FeedbackItem(
                priority: gap.priority,
                icon: "📐",
                message: "기울기 조정",
                category: "tilt",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        // 기울기 방향 수정 ✅
        // atan2로 계산된 각도: 양수=반시계(왼쪽), 음수=시계(오른쪽)
        // current > target: 더 반시계 방향 → 시계 방향(오른쪽)으로 기울여야 함
        // current < target: 더 시계 방향 → 반시계 방향(왼쪽)으로 기울여야 함
        let direction = current > target ? "오른쪽" : "왼쪽"
        return FeedbackItem(
            priority: gap.priority,
            icon: "📐",
            message: "카메라를 \(direction)으로 기울여주세요",
            category: "tilt",
            currentValue: current,
            targetValue: target,
            tolerance: gap.tolerance,
            unit: "도"
        )
    }

    /// 얼굴 각도 피드백
    private func generateFaceYawFeedback(gap: Gap) -> FeedbackItem {
        guard let current = gap.current, let target = gap.target else {
            return FeedbackItem(
                priority: gap.priority,
                icon: "👤",
                message: "얼굴 각도 조정",
                category: "face_yaw",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        let direction = current > target ? "왼쪽" : "오른쪽"
        return FeedbackItem(
            priority: gap.priority,
            icon: "👤",
            message: "고개를 \(direction)으로 돌려주세요",
            category: "face_yaw",
            currentValue: current,
            targetValue: target,
            tolerance: gap.tolerance,
            unit: "도"
        )
    }

    /// 카메라 앵글 피드백
    private func generateCameraAngleFeedback(gap: Gap) -> FeedbackItem? {
        guard let metadata = gap.metadata,
              let refAngle = metadata["reference_angle"] as? CameraAngle,
              let curAngle = metadata["current_angle"] as? CameraAngle else {
            return nil
        }

        if let message = cameraAngleDetector.generateAngleFeedback(
            reference: refAngle,
            current: curAngle
        ) {
            return FeedbackItem(
                priority: gap.priority,
                icon: "📷",
                message: message,
                category: "camera_angle",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        return nil
    }

    /// 시선 피드백
    private func generateGazeFeedback(gap: Gap) -> FeedbackItem? {
        guard let metadata = gap.metadata,
              let refGaze = metadata["reference_gaze"] as? GazeDirection,
              let _ = metadata["current_gaze"] as? GazeDirection else {
            return nil
        }

        let message: String
        switch refGaze {
        case .lookingAtCamera:
            message = "카메라를 바라봐주세요"
        case .lookingLeft:
            message = "시선을 왼쪽으로"
        case .lookingRight:
            message = "시선을 오른쪽으로"
        case .lookingUp:
            message = "시선을 위로"
        case .lookingDown:
            message = "시선을 아래로"
        default:
            message = "시선 방향 조정"
        }

        return FeedbackItem(
            priority: gap.priority,
            icon: "👀",
            message: message,
            category: "gaze",
            currentValue: nil,
            targetValue: nil,
            tolerance: nil,
            unit: nil
        )
    }

    /// 구도 피드백
    private func generateCompositionFeedback(
        gap: Gap,
        reference: FrameAnalysis,
        current: (
            face: FaceAnalysisResult?,
            pose: PoseAnalysisResult?,
            bodyRect: CGRect?,
            brightness: Float,
            tilt: Float,
            cameraAngle: CameraAngle,
            compositionType: CompositionType?,
            gaze: GazeResult?,
            depth: DepthResult?
        )
    ) -> FeedbackItem? {

        guard let refComp = reference.compositionType,
              let refFace = reference.faceRect,
              let curFace = current.face?.faceRect else {
            return nil
        }

        let refPosition = CGPoint(x: refFace.midX, y: refFace.midY)
        let curPosition = CGPoint(x: curFace.midX, y: curFace.midY)

        let (message, _, _) = compositionAnalyzer.generateCompositionFeedback(
            referenceType: refComp,
            referencePosition: refPosition,
            currentPosition: curPosition
        )

        return FeedbackItem(
            priority: gap.priority,
            icon: "🎨",
            message: message,
            category: "composition",
            currentValue: nil,
            targetValue: nil,
            tolerance: nil,
            unit: nil
        )
    }

    /// 화면 비율 피드백 생성
    private func generateAspectRatioFeedback(gap: Gap) -> FeedbackItem? {
        guard let metadata = gap.metadata,
              let refRatio = metadata["reference_ratio"] as? CameraAspectRatio,
              let curRatio = metadata["current_ratio"] as? CameraAspectRatio else {
            return nil
        }

        let message = "화면 비율을 \(refRatio.displayName)로 변경하세요 (현재: \(curRatio.displayName))"

        return FeedbackItem(
            priority: gap.priority,
            icon: "📐",
            message: message,
            category: "aspect_ratio",
            currentValue: nil,
            targetValue: nil,
            tolerance: nil,
            unit: nil
        )
    }

    /// 여백 피드백 생성
    private func generatePaddingFeedback(gap: Gap) -> FeedbackItem? {
        guard let metadata = gap.metadata,
              let top = metadata["top"] as? CGFloat,
              let bottom = metadata["bottom"] as? CGFloat,
              let left = metadata["left"] as? CGFloat,
              let right = metadata["right"] as? CGFloat else {
            return nil
        }

        // 가장 큰 여백 방향 찾기
        let paddings = [
            ("상단", top),
            ("하단", bottom),
            ("좌측", left),
            ("우측", right)
        ]
        let maxPadding = paddings.max(by: { $0.1 < $1.1 })!

        let message: String
        if maxPadding.1 > 0.15 {
            message = "\(maxPadding.0) 여백이 너무 많습니다. 줌인하거나 위치를 조정하세요"
        } else {
            message = "불필요한 여백을 줄이세요 (줌인 또는 위치 조정)"
        }

        return FeedbackItem(
            priority: gap.priority,
            icon: "↔️",
            message: message,
            category: "padding",
            currentValue: gap.current,
            targetValue: gap.target,
            tolerance: gap.tolerance,
            unit: "%"
        )
    }
}
