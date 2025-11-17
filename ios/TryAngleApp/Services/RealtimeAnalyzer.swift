import Foundation
import Vision
import UIKit
import CoreImage
import Combine

// MARK: - 실시간 분석을 위한 데이터 구조
struct FrameAnalysis {
    let faceRect: CGRect?          // 얼굴 위치 (정규화된 좌표)
    let bodyRect: CGRect?          // 전신 추정 영역
    let brightness: Float          // 평균 밝기
    let tiltAngle: Float           // 기울기 각도
    let faceYaw: Float?            // 얼굴 좌우 회전 (정면=0)
    let facePitch: Float?          // 얼굴 상하 각도
    let cameraAngle: String?       // 카메라 각도 (high/low/front)
    let poseKeypoints: [CGPoint]?  // 포즈 키포인트 (코, 어깨, 팔꿈치 등)
}

// MARK: - 실시간 피드백 생성기
class RealtimeAnalyzer: ObservableObject {
    @Published var instantFeedback: [FeedbackItem] = []
    @Published var isPerfect: Bool = false  // 완벽한 상태 감지
    @Published var perfectScore: Double = 0.0  // 완성도 점수 (0~1)

    private var referenceAnalysis: FrameAnalysis?
    private var lastAnalysisTime = Date()
    private let analysisInterval: TimeInterval = 0.1  // 100ms마다 분석

    // 히스테리시스를 위한 상태 추적
    private var feedbackHistory: [String: Int] = [:]  // 카테고리별 연속 감지 횟수
    private let historyThreshold = 3  // 3번 연속 감지되어야 표시
    private var perfectFrameCount = 0  // 완벽한 프레임 연속 횟수
    private let perfectThreshold = 10  // 10프레임(약 1초) 연속 완벽해야 감지

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

    // MARK: - 레퍼런스 이미지 분석
    func analyzeReference(_ image: UIImage) {
        guard let cgImage = image.cgImage else { return }

        // Vision 요청 실행
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        try? handler.perform([faceDetectionRequest, poseDetectionRequest])

        // 얼굴 영역 및 각도 추출
        let faceObservation = faceDetectionRequest.results?.first
        let faceRect = faceObservation?.boundingBox
        let faceYaw = faceObservation?.yaw?.floatValue
        let facePitch = faceObservation?.pitch?.floatValue

        // 포즈 키포인트 추출
        let poseKeypoints = extractPoseKeypoints(from: poseDetectionRequest.results?.first)

        // 밝기 계산
        let brightness = calculateBrightness(cgImage)

        // 기울기 계산
        let tiltAngle = calculateTilt(cgImage)

        // 전신 영역 추정 (얼굴 기준)
        let bodyRect = estimateBodyRect(from: faceRect)

        // 카메라 각도 추정 (얼굴 위치 기반)
        let cameraAngle = estimateCameraAngle(faceRect: faceRect, facePitch: facePitch)

        referenceAnalysis = FrameAnalysis(
            faceRect: faceRect,
            bodyRect: bodyRect,
            brightness: brightness,
            tiltAngle: tiltAngle,
            faceYaw: faceYaw,
            facePitch: facePitch,
            cameraAngle: cameraAngle,
            poseKeypoints: poseKeypoints
        )

        print("📸 레퍼런스 분석 완료:")
        print("   - 얼굴: \(faceRect != nil ? "감지됨" : "없음")")
        print("   - 얼굴 각도: yaw=\(faceYaw ?? 0), pitch=\(facePitch ?? 0)")
        print("   - 카메라 앵글: \(cameraAngle ?? "알 수 없음")")
        print("   - 포즈 키포인트: \(poseKeypoints?.count ?? 0)개")
        print("   - 밝기: \(brightness)")
        print("   - 기울기: \(tiltAngle)도")
    }

    // MARK: - 실시간 프레임 분석
    func analyzeFrame(_ image: UIImage) {
        // 너무 자주 분석하지 않도록 제한
        guard Date().timeIntervalSince(lastAnalysisTime) >= analysisInterval else { return }

        // 레퍼런스가 없으면 분석하지 않음 (중요!)
        guard let reference = referenceAnalysis else {
            // 레퍼런스 없으면 피드백 초기화
            DispatchQueue.main.async {
                self.instantFeedback = []
                self.perfectScore = 0.0
                self.isPerfect = false
            }
            return
        }

        guard let cgImage = image.cgImage else { return }

        lastAnalysisTime = Date()

        // 빠른 Vision 분석
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        try? handler.perform([faceDetectionRequest, poseDetectionRequest])

        let faceObservation = faceDetectionRequest.results?.first
        let currentFaceRect = faceObservation?.boundingBox
        let currentFaceYaw = faceObservation?.yaw?.floatValue
        let currentFacePitch = faceObservation?.pitch?.floatValue
        let currentBodyRect = estimateBodyRect(from: currentFaceRect)
        let currentTilt = calculateTilt(cgImage)
        let currentPoseKeypoints = extractPoseKeypoints(from: poseDetectionRequest.results?.first)
        let currentCameraAngle = estimateCameraAngle(faceRect: currentFaceRect, facePitch: currentFacePitch)

        var feedback: [FeedbackItem] = []

        // 1순위: 프레이밍 (거리 기반) 피드백
        if let refBody = reference.bodyRect, let curBody = currentBodyRect {
            let refSize = refBody.width * refBody.height
            let curSize = curBody.width * curBody.height
            let sizeRatio = curSize / refSize

            // 거리 기반 피드백 (줌이 아닌 걸음 수)
            if sizeRatio < 0.7 {  // 피사체가 작음 → 가까이 가야 함
                let distanceFactor = 1.0 / sizeRatio
                let estimatedDistanceM: Float = 2.5  // 평균 촬영 거리
                let distanceChangeM = estimatedDistanceM * (distanceFactor - 1.0)
                let steps = max(1, Int(round(distanceChangeM / 0.7)))  // 0.7m per step

                feedback.append(FeedbackItem(
                    priority: 1,
                    icon: "🚶",
                    message: "\(steps)걸음 앞으로",
                    category: "distance_closer",
                    currentValue: Double(curSize * 100),
                    targetValue: Double(refSize * 100),
                    tolerance: 10.0,
                    unit: "%"
                ))
            } else if sizeRatio > 1.4 {  // 피사체가 큼 → 멀리 가야 함
                let distanceFactor = sizeRatio
                let estimatedDistanceM: Float = 2.5
                let distanceChangeM = estimatedDistanceM * (distanceFactor - 1.0)
                let steps = max(1, Int(round(distanceChangeM / 0.7)))

                feedback.append(FeedbackItem(
                    priority: 1,
                    icon: "🚶",
                    message: "\(steps)걸음 뒤로",
                    category: "distance_farther",
                    currentValue: Double(curSize * 100),
                    targetValue: Double(refSize * 100),
                    tolerance: 10.0,
                    unit: "%"
                ))
            }
        }

        // 2순위: 구도 (위치) 피드백
        if let refFace = reference.faceRect, let curFace = currentFaceRect {
            let xDiff = (curFace.midX - refFace.midX) * 100
            let yDiff = (curFace.midY - refFace.midY) * 100

            if abs(xDiff) > 5 {  // 5% 이상 차이
                let direction = xDiff > 0 ? "왼쪽으로" : "오른쪽으로"
                feedback.append(FeedbackItem(
                    priority: 2,
                    icon: "↔️",
                    message: "\(direction) 이동",
                    category: "position_x",
                    currentValue: Double(curFace.midX * 100),
                    targetValue: Double(refFace.midX * 100),
                    tolerance: 5.0,
                    unit: "%"
                ))
            }

            if abs(yDiff) > 5 {
                let direction = yDiff > 0 ? "아래로" : "위로"
                feedback.append(FeedbackItem(
                    priority: 2,
                    icon: "↕️",
                    message: "\(direction) 이동",
                    category: "position_y",
                    currentValue: Double(curFace.midY * 100),
                    targetValue: Double(refFace.midY * 100),
                    tolerance: 5.0,
                    unit: "%"
                ))
            }
        }

        // 3순위: 기울기 피드백
        let tiltDiff = currentTilt - reference.tiltAngle
        if abs(tiltDiff) > 3 {
            let direction = tiltDiff > 0 ? "왼쪽" : "오른쪽"
            feedback.append(FeedbackItem(
                priority: 3,
                icon: "📐",
                message: "\(direction)으로 회전",
                category: "tilt",
                currentValue: Double(currentTilt),
                targetValue: Double(reference.tiltAngle),
                tolerance: 3.0,
                unit: "도"
            ))
        }

        // 4순위: 얼굴 각도 피드백
        if let refYaw = reference.faceYaw, let curYaw = currentFaceYaw {
            let yawDiff = (curYaw - refYaw) * 180 / .pi  // 라디안 → 도
            if abs(yawDiff) > 10 {  // 10도 이상 차이
                let direction = yawDiff > 0 ? "왼쪽" : "오른쪽"
                feedback.append(FeedbackItem(
                    priority: 4,
                    icon: "👤",
                    message: "얼굴을 \(direction)으로",
                    category: "face_yaw",
                    currentValue: Double(curYaw * 180 / .pi),
                    targetValue: Double(refYaw * 180 / .pi),
                    tolerance: 10.0,
                    unit: "도"
                ))
            }
        }

        // 5순위: 카메라 각도 피드백
        if let refAngle = reference.cameraAngle, let curAngle = currentCameraAngle {
            if refAngle != curAngle {
                var message = ""
                if refAngle == "low" && curAngle != "low" {
                    message = "카메라를 낮춰주세요 (로우앵글)"
                } else if refAngle == "high" && curAngle != "high" {
                    message = "카메라를 높여주세요 (하이앵글)"
                } else if refAngle == "front" && curAngle != "front" {
                    message = "카메라를 정면 높이로"
                }

                if !message.isEmpty {
                    feedback.append(FeedbackItem(
                        priority: 5,
                        icon: "📷",
                        message: message,
                        category: "camera_angle",
                        currentValue: nil,
                        targetValue: nil,
                        tolerance: nil,
                        unit: nil
                    ))
                }
            }
        }

        // 6순위: 포즈 피드백 (팔, 다리 각도)
        if let refPose = reference.poseKeypoints, let curPose = currentPoseKeypoints {
            if refPose.count >= 13 && curPose.count >= 13 {
                // 주요 관절 비교 (어깨, 팔꿈치, 손목 등)
                let poseDiff = comparePoseKeypoints(reference: refPose, current: curPose)
                for diff in poseDiff {
                    feedback.append(diff)
                }
            }
        }

        // 히스테리시스 적용: 연속으로 감지된 피드백만 표시
        var stableFeedback: [FeedbackItem] = []
        var currentCategories = Set<String>()

        for fb in feedback {
            currentCategories.insert(fb.category)
            feedbackHistory[fb.category, default: 0] += 1

            // 히스테리시스 임계값 넘으면 표시
            if feedbackHistory[fb.category]! >= historyThreshold {
                stableFeedback.append(fb)
            }
        }

        // 사라진 카테고리는 히스토리 초기화
        for (category, _) in feedbackHistory {
            if !currentCategories.contains(category) {
                feedbackHistory[category] = 0
            }
        }

        // 완벽한 상태 감지
        let score = calculatePerfectScore(feedback: feedback)
        let isCurrentlyPerfect = stableFeedback.isEmpty && score > 0.95

        if isCurrentlyPerfect {
            perfectFrameCount += 1
        } else {
            perfectFrameCount = 0
        }

        // 즉시 피드백 업데이트
        DispatchQueue.main.async {
            self.instantFeedback = stableFeedback
            self.perfectScore = score
            self.isPerfect = self.perfectFrameCount >= self.perfectThreshold
        }
    }

    // MARK: - Helper Functions

    private func calculatePerfectScore(feedback: [FeedbackItem]) -> Double {
        // 피드백이 없으면 완벽
        if feedback.isEmpty {
            return 1.0
        }

        // 각 피드백의 완성도 계산
        var totalScore = 0.0
        var count = 0

        for fb in feedback {
            if let current = fb.currentValue,
               let target = fb.targetValue {
                let diff = abs(current - target)
                let maxDiff = max(abs(target) + 50, 100.0)  // 최대 차이
                let itemScore = max(0.0, 1.0 - (diff / maxDiff))
                totalScore += itemScore
                count += 1
            }
        }

        if count == 0 {
            return 0.0
        }

        // 평균 점수
        return totalScore / Double(count)
    }

    private func calculateBrightness(_ cgImage: CGImage) -> Float {
        // 간단한 밝기 계산 (샘플링)
        let width = min(cgImage.width, 100)  // 샘플링으로 속도 향상
        let height = min(cgImage.height, 100)

        guard let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return 0.5 }

        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        guard let data = context.data else { return 0.5 }

        let buffer = data.bindMemory(to: UInt8.self, capacity: width * height * 4)
        var totalBrightness: Float = 0

        for i in stride(from: 0, to: width * height * 4, by: 4) {
            let r = Float(buffer[i]) / 255.0
            let g = Float(buffer[i + 1]) / 255.0
            let b = Float(buffer[i + 2]) / 255.0
            totalBrightness += (r + g + b) / 3.0
        }

        return totalBrightness / Float(width * height)
    }

    private func calculateTilt(_ cgImage: CGImage) -> Float {
        // 간단한 기울기 추정 (엣지 검출 기반)
        // 실제로는 더 복잡한 알고리즘 필요하지만 속도를 위해 간단하게
        return 0.0  // TODO: 구현 필요
    }

    private func estimateBodyRect(from faceRect: CGRect?) -> CGRect? {
        // 얼굴 위치로부터 전신 영역 추정
        guard let face = faceRect else { return nil }

        // 일반적으로 얼굴이 전신의 1/7 정도
        let bodyWidth = face.width * 3
        let bodyHeight = face.height * 7
        let bodyX = face.midX - bodyWidth / 2
        let bodyY = face.minY  // 얼굴 아래로 확장

        return CGRect(x: bodyX, y: bodyY, width: bodyWidth, height: bodyHeight)
    }

    // MARK: - 포즈 및 각도 분석 헬퍼

    private func extractPoseKeypoints(from observation: VNHumanBodyPoseObservation?) -> [CGPoint]? {
        guard let observation = observation else { return nil }

        var keypoints: [CGPoint] = []

        // VNHumanBodyPoseObservation의 주요 키포인트 추출
        let jointNames: [VNHumanBodyPoseObservation.JointName] = [
            .nose,           // 0: 코
            .leftEye,        // 1: 왼쪽 눈
            .rightEye,       // 2: 오른쪽 눈
            .leftEar,        // 3: 왼쪽 귀
            .rightEar,       // 4: 오른쪽 귀
            .leftShoulder,   // 5: 왼쪽 어깨
            .rightShoulder,  // 6: 오른쪽 어깨
            .leftElbow,      // 7: 왼쪽 팔꿈치
            .rightElbow,     // 8: 오른쪽 팔꿈치
            .leftWrist,      // 9: 왼쪽 손목
            .rightWrist,     // 10: 오른쪽 손목
            .leftHip,        // 11: 왼쪽 골반
            .rightHip,       // 12: 오른쪽 골반
            .leftKnee,       // 13: 왼쪽 무릎
            .rightKnee,      // 14: 오른쪽 무릎
            .leftAnkle,      // 15: 왼쪽 발목
            .rightAnkle      // 16: 오른쪽 발목
        ]

        for jointName in jointNames {
            if let point = try? observation.recognizedPoint(jointName),
               point.confidence > 0.3 {  // 신뢰도 30% 이상만 사용
                keypoints.append(point.location)
            } else {
                keypoints.append(.zero)  // 감지 실패 시 (0, 0)
            }
        }

        return keypoints.isEmpty ? nil : keypoints
    }

    private func estimateCameraAngle(faceRect: CGRect?, facePitch: Float?) -> String? {
        guard let face = faceRect else { return nil }

        // 얼굴 위치 기반 카메라 각도 추정
        let faceY = face.midY

        // 화면 상단 1/3: 로우앵글 (카메라가 낮음)
        // 화면 중간 1/3: 정면
        // 화면 하단 1/3: 하이앵글 (카메라가 높음)
        if faceY < 0.33 {
            return "low"   // 로우앵글
        } else if faceY > 0.67 {
            return "high"  // 하이앵글
        } else {
            return "front" // 정면
        }
    }

    private func comparePoseKeypoints(reference: [CGPoint], current: [CGPoint]) -> [FeedbackItem] {
        var poseFeedback: [FeedbackItem] = []

        // 최소 17개 키포인트 필요 (코, 눈, 귀, 어깨, 팔꿈치, 손목, 골반, 무릎, 발목)
        guard reference.count >= 17, current.count >= 17 else { return [] }

        // 주요 포즈 비교 (어깨, 팔꿈치, 손목)
        // 왼쪽 팔 각도
        if reference[5] != .zero && reference[7] != .zero && reference[9] != .zero &&
           current[5] != .zero && current[7] != .zero && current[9] != .zero {

            let refLeftArmAngle = calculateAngle(
                p1: reference[5],  // 왼쪽 어깨
                p2: reference[7],  // 왼쪽 팔꿈치
                p3: reference[9]   // 왼쪽 손목
            )

            let curLeftArmAngle = calculateAngle(
                p1: current[5],
                p2: current[7],
                p3: current[9]
            )

            let angleDiff = abs(refLeftArmAngle - curLeftArmAngle)
            if angleDiff > 15 {  // 15도 이상 차이
                let direction = curLeftArmAngle > refLeftArmAngle ? "펴세요" : "구부리세요"
                poseFeedback.append(FeedbackItem(
                    priority: 6,
                    icon: "💪",
                    message: "왼팔을 \(direction)",
                    category: "pose_left_arm",
                    currentValue: Double(curLeftArmAngle),
                    targetValue: Double(refLeftArmAngle),
                    tolerance: 15.0,
                    unit: "도"
                ))
            }
        }

        // 오른쪽 팔 각도
        if reference[6] != .zero && reference[8] != .zero && reference[10] != .zero &&
           current[6] != .zero && current[8] != .zero && current[10] != .zero {

            let refRightArmAngle = calculateAngle(
                p1: reference[6],  // 오른쪽 어깨
                p2: reference[8],  // 오른쪽 팔꿈치
                p3: reference[10]  // 오른쪽 손목
            )

            let curRightArmAngle = calculateAngle(
                p1: current[6],
                p2: current[8],
                p3: current[10]
            )

            let angleDiff = abs(refRightArmAngle - curRightArmAngle)
            if angleDiff > 15 {
                let direction = curRightArmAngle > refRightArmAngle ? "펴세요" : "구부리세요"
                poseFeedback.append(FeedbackItem(
                    priority: 6,
                    icon: "💪",
                    message: "오른팔을 \(direction)",
                    category: "pose_right_arm",
                    currentValue: Double(curRightArmAngle),
                    targetValue: Double(refRightArmAngle),
                    tolerance: 15.0,
                    unit: "도"
                ))
            }
        }

        return poseFeedback
    }

    private func calculateAngle(p1: CGPoint, p2: CGPoint, p3: CGPoint) -> Float {
        // 세 점으로 각도 계산 (p2가 꼭짓점)
        let v1 = CGVector(dx: p1.x - p2.x, dy: p1.y - p2.y)
        let v2 = CGVector(dx: p3.x - p2.x, dy: p3.y - p2.y)

        let dot = v1.dx * v2.dx + v1.dy * v2.dy
        let mag1 = sqrt(v1.dx * v1.dx + v1.dy * v1.dy)
        let mag2 = sqrt(v2.dx * v2.dx + v2.dy * v2.dy)

        let cosAngle = dot / (mag1 * mag2)
        let angleRad = acos(max(-1, min(1, cosAngle)))  // -1~1 범위로 제한
        let angleDeg = Float(angleRad * 180 / .pi)

        return angleDeg
    }
}