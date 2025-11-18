import Foundation

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

            let poseComparison = poseComparator.comparePoses(
                referenceKeypoints: refPose,
                currentKeypoints: curPose
            )

            let poseFeedbacks = poseComparator.generateFeedback(from: poseComparison)
            for (message, category) in poseFeedbacks {
                feedbacks.append(FeedbackItem(
                    priority: 6,
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
                message: "좌우 위치 조정",
                category: "position_x",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        let direction = current > target ? "왼쪽으로" : "오른쪽으로"
        return FeedbackItem(
            priority: gap.priority,
            icon: "↔️",
            message: "\(direction) 이동",
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
                message: "상하 위치 조정",
                category: "position_y",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )
        }

        let direction = current > target ? "아래로" : "위로"
        return FeedbackItem(
            priority: gap.priority,
            icon: "↕️",
            message: "\(direction) 이동",
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

        let direction = current > target ? "왼쪽" : "오른쪽"
        return FeedbackItem(
            priority: gap.priority,
            icon: "📐",
            message: "\(direction)으로 회전 (더치 틸트)",
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
            message: "얼굴을 \(direction)으로",
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
              let curGaze = metadata["current_gaze"] as? GazeDirection else {
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

        let (message, xDir, yDir) = compositionAnalyzer.generateCompositionFeedback(
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
}
