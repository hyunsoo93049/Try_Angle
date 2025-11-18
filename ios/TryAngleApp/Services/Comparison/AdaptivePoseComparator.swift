import Foundation
import Vision
import CoreGraphics

// MARK: - 포즈 타입
enum PoseType {
    case fullBody        // 전신 (머리 ~ 발목)
    case upperBody       // 상반신 (머리 ~ 골반)
    case portrait        // 흉상 (머리 ~ 어깨)
    case unknown         // 감지 실패

    var description: String {
        switch self {
        case .fullBody:
            return "전신"
        case .upperBody:
            return "상반신"
        case .portrait:
            return "흉상"
        case .unknown:
            return "알 수 없음"
        }
    }
}

// MARK: - 키포인트 그룹
enum KeypointGroup: String {
    case head           // 머리 (코, 눈, 귀)
    case shoulders      // 어깨
    case arms           // 팔 (팔꿈치, 손목)
    case torso          // 몸통 (골반)
    case legs           // 다리 (무릎, 발목)

    var keypointIndices: [Int] {
        switch self {
        case .head:
            return [0, 1, 2, 3, 4]  // 코, 눈, 귀
        case .shoulders:
            return [5, 6]           // 어깨
        case .arms:
            return [7, 8, 9, 10]    // 팔꿈치, 손목
        case .torso:
            return [11, 12]         // 골반
        case .legs:
            return [13, 14, 15, 16] // 무릎, 발목
        }
    }
}

// MARK: - 포즈 비교 결과
struct PoseComparisonResult {
    let poseType: PoseType                  // 감지된 포즈 타입
    let visibleGroups: [KeypointGroup]      // 보이는 신체 부위
    let missingGroups: [KeypointGroup]      // 안 보이는 신체 부위
    let comparableKeypoints: [Int]          // 비교 가능한 키포인트 인덱스
    let angleDifferences: [String: Float]   // 각 부위별 각도 차이
    let overallAccuracy: Double             // 전체 정확도 (0~1)
}

// MARK: - 적응형 포즈 비교기
class AdaptivePoseComparator {

    private let confidenceThreshold: Float = 0.5  // 신뢰도 임계값

    /// Vision 키포인트 순서 (17개)
    private let keypointNames: [String] = [
        "nose",           // 0
        "leftEye",        // 1
        "rightEye",       // 2
        "leftEar",        // 3
        "rightEar",       // 4
        "leftShoulder",   // 5
        "rightShoulder",  // 6
        "leftElbow",      // 7
        "rightElbow",     // 8
        "leftWrist",      // 9
        "rightWrist",     // 10
        "leftHip",        // 11
        "rightHip",       // 12
        "leftKnee",       // 13
        "rightKnee",      // 14
        "leftAnkle",      // 15
        "rightAnkle"      // 16
    ]

    /// 레퍼런스와 현재 포즈 적응형 비교
    /// - Parameters:
    ///   - referenceKeypoints: 레퍼런스 키포인트 (17개, confidence 포함)
    ///   - currentKeypoints: 현재 키포인트 (17개, confidence 포함)
    /// - Returns: 비교 결과
    func comparePoses(
        referenceKeypoints: [(point: CGPoint, confidence: Float)],
        currentKeypoints: [(point: CGPoint, confidence: Float)]
    ) -> PoseComparisonResult {

        // 1. 보이는 키포인트 필터링
        let visibleRefIndices = filterVisibleKeypoints(referenceKeypoints)
        let visibleCurIndices = filterVisibleKeypoints(currentKeypoints)

        // 2. 공통으로 보이는 키포인트만 추출
        let comparableIndices = Set(visibleRefIndices).intersection(visibleCurIndices)

        // 3. 포즈 타입 자동 감지
        _ = detectPoseType(visibleIndices: Array(comparableIndices))
        let currentPoseType = detectPoseType(visibleIndices: Array(comparableIndices))

        // 4. 보이는/안 보이는 그룹 분류
        let visibleGroups = classifyVisibleGroups(visibleIndices: Array(comparableIndices))
        let allGroups: Set<KeypointGroup> = [.head, .shoulders, .arms, .torso, .legs]
        let missingGroups = Array(allGroups.subtracting(visibleGroups))

        // 5. 각 부위별 각도 차이 계산
        var angleDifferences: [String: Float] = [:]

        // 왼팔 각도
        if canCompareLeftArm(indices: comparableIndices) {
            let refAngle = calculateArmAngle(
                shoulder: referenceKeypoints[5].point,
                elbow: referenceKeypoints[7].point,
                wrist: referenceKeypoints[9].point
            )
            let curAngle = calculateArmAngle(
                shoulder: currentKeypoints[5].point,
                elbow: currentKeypoints[7].point,
                wrist: currentKeypoints[9].point
            )
            angleDifferences["left_arm"] = abs(refAngle - curAngle)
        }

        // 오른팔 각도
        if canCompareRightArm(indices: comparableIndices) {
            let refAngle = calculateArmAngle(
                shoulder: referenceKeypoints[6].point,
                elbow: referenceKeypoints[8].point,
                wrist: referenceKeypoints[10].point
            )
            let curAngle = calculateArmAngle(
                shoulder: currentKeypoints[6].point,
                elbow: currentKeypoints[8].point,
                wrist: currentKeypoints[10].point
            )
            angleDifferences["right_arm"] = abs(refAngle - curAngle)
        }

        // 왼다리 각도
        if canCompareLeftLeg(indices: comparableIndices) {
            let refAngle = calculateLegAngle(
                hip: referenceKeypoints[11].point,
                knee: referenceKeypoints[13].point,
                ankle: referenceKeypoints[15].point
            )
            let curAngle = calculateLegAngle(
                hip: currentKeypoints[11].point,
                knee: currentKeypoints[13].point,
                ankle: currentKeypoints[15].point
            )
            angleDifferences["left_leg"] = abs(refAngle - curAngle)
        }

        // 오른다리 각도
        if canCompareRightLeg(indices: comparableIndices) {
            let refAngle = calculateLegAngle(
                hip: referenceKeypoints[12].point,
                knee: referenceKeypoints[14].point,
                ankle: referenceKeypoints[16].point
            )
            let curAngle = calculateLegAngle(
                hip: currentKeypoints[12].point,
                knee: currentKeypoints[14].point,
                ankle: currentKeypoints[16].point
            )
            angleDifferences["right_leg"] = abs(refAngle - curAngle)
        }

        // 6. 전체 정확도 계산
        let accuracy = calculateOverallAccuracy(angleDifferences: angleDifferences)

        return PoseComparisonResult(
            poseType: currentPoseType,
            visibleGroups: visibleGroups,
            missingGroups: missingGroups,
            comparableKeypoints: Array(comparableIndices).sorted(),
            angleDifferences: angleDifferences,
            overallAccuracy: accuracy
        )
    }

    /// 포즈 비교 결과로부터 피드백 생성
    /// - Parameters:
    ///   - currentResult: 현재 프레임의 비교 결과
    ///   - referenceResult: 레퍼런스의 비교 결과 (어떤 부위가 있는지 확인용)
    /// - Returns: 피드백 아이템 배열
    func generateFeedback(
        from currentResult: PoseComparisonResult,
        referenceResult: PoseComparisonResult
    ) -> [(message: String, category: String)] {
        var feedback: [(message: String, category: String)] = []

        // 1. 레퍼런스와 현재 모두에서 보이는 부위만 비교
        let referenceVisibleGroups = Set(referenceResult.visibleGroups)
        let currentVisibleGroups = Set(currentResult.visibleGroups)

        // 레퍼런스에 있지만 현재 없는 중요 부위만 알림
        let missingImportantGroups = referenceVisibleGroups.subtracting(currentVisibleGroups)

        // 포즈 타입별로 중요한 부위 정의
        let importantGroups: Set<KeypointGroup>
        switch referenceResult.poseType {
        case .fullBody:
            importantGroups = [.head, .shoulders, .arms, .torso, .legs]
        case .upperBody:
            importantGroups = [.head, .shoulders, .arms, .torso]
        case .portrait:
            importantGroups = [.head, .shoulders]
        case .unknown:
            importantGroups = []
        }

        // 중요한 부위 중 빠진 것만 피드백
        let actuallyMissing = missingImportantGroups.intersection(importantGroups)

        if !actuallyMissing.isEmpty && actuallyMissing.count > 1 {
            // 너무 많은 부위가 안 보이면 전체적인 피드백
            feedback.append((
                message: "화면에 포즈가 잘 보이도록 조정해주세요",
                category: "pose_not_visible"
            ))
            return feedback  // 포즈가 제대로 안 보이면 다른 피드백 생략
        }

        // 2. 🔄 각도 차이 피드백 (구체적인 각도 정보 포함)
        let angleTolerance: Float = 15.0  // 15도 허용

        if let leftArmDiff = currentResult.angleDifferences["left_arm"],
           abs(leftArmDiff) > angleTolerance {
            let direction = leftArmDiff > 0 ? "더 올려주세요" : "더 내려주세요"
            let message = "왼팔을 \(direction) (약 \(Int(abs(leftArmDiff)))도)"
            feedback.append((message: message, category: "pose_left_arm"))
        }

        if let rightArmDiff = currentResult.angleDifferences["right_arm"],
           abs(rightArmDiff) > angleTolerance {
            let direction = rightArmDiff > 0 ? "더 올려주세요" : "더 내려주세요"
            let message = "오른팔을 \(direction) (약 \(Int(abs(rightArmDiff)))도)"
            feedback.append((message: message, category: "pose_right_arm"))
        }

        if let leftLegDiff = currentResult.angleDifferences["left_leg"],
           abs(leftLegDiff) > angleTolerance {
            let direction = leftLegDiff > 0 ? "더 굽혀주세요" : "더 펴주세요"
            let message = "왼다리를 \(direction) (약 \(Int(abs(leftLegDiff)))도)"
            feedback.append((message: message, category: "pose_left_leg"))
        }

        if let rightLegDiff = currentResult.angleDifferences["right_leg"],
           abs(rightLegDiff) > angleTolerance {
            let direction = rightLegDiff > 0 ? "더 굽혀주세요" : "더 펴주세요"
            let message = "오른다리를 \(direction) (약 \(Int(abs(rightLegDiff)))도)"
            feedback.append((message: message, category: "pose_right_leg"))
        }

        return feedback
    }

    // MARK: - Private Helpers

    /// 신뢰도 임계값 이상의 키포인트만 필터링
    private func filterVisibleKeypoints(
        _ keypoints: [(point: CGPoint, confidence: Float)]
    ) -> [Int] {
        return keypoints.enumerated().compactMap { index, kp in
            kp.confidence >= confidenceThreshold ? index : nil
        }
    }

    /// 포즈 타입 자동 감지
    private func detectPoseType(visibleIndices: [Int]) -> PoseType {
        let hasHead = visibleIndices.contains(where: { [0, 1, 2, 3, 4].contains($0) })
        let hasShoulders = visibleIndices.contains(5) || visibleIndices.contains(6)
        let hasTorso = visibleIndices.contains(11) || visibleIndices.contains(12)
        let hasLegs = visibleIndices.contains(where: { [13, 14, 15, 16].contains($0) })

        if hasHead && hasShoulders && hasTorso && hasLegs {
            return .fullBody
        } else if hasHead && hasShoulders && hasTorso {
            return .upperBody
        } else if hasHead && hasShoulders {
            return .portrait
        } else {
            return .unknown
        }
    }

    /// 보이는 신체 그룹 분류
    private func classifyVisibleGroups(visibleIndices: [Int]) -> [KeypointGroup] {
        var groups: [KeypointGroup] = []

        for group in [KeypointGroup.head, .shoulders, .arms, .torso, .legs] {
            let groupIndices = group.keypointIndices
            let visibleCount = groupIndices.filter { visibleIndices.contains($0) }.count

            // 그룹의 50% 이상이 보이면 "보임"으로 간주
            if Double(visibleCount) / Double(groupIndices.count) >= 0.5 {
                groups.append(group)
            }
        }

        return groups
    }

    /// 왼팔 비교 가능 여부
    private func canCompareLeftArm(indices: Set<Int>) -> Bool {
        return indices.contains(5) && indices.contains(7) && indices.contains(9)
    }

    /// 오른팔 비교 가능 여부
    private func canCompareRightArm(indices: Set<Int>) -> Bool {
        return indices.contains(6) && indices.contains(8) && indices.contains(10)
    }

    /// 왼다리 비교 가능 여부
    private func canCompareLeftLeg(indices: Set<Int>) -> Bool {
        return indices.contains(11) && indices.contains(13) && indices.contains(15)
    }

    /// 오른다리 비교 가능 여부
    private func canCompareRightLeg(indices: Set<Int>) -> Bool {
        return indices.contains(12) && indices.contains(14) && indices.contains(16)
    }

    /// 팔 각도 계산 (어깨-팔꿈치-손목)
    private func calculateArmAngle(
        shoulder: CGPoint,
        elbow: CGPoint,
        wrist: CGPoint
    ) -> Float {
        return calculateAngle(p1: shoulder, p2: elbow, p3: wrist)
    }

    /// 다리 각도 계산 (골반-무릎-발목)
    private func calculateLegAngle(
        hip: CGPoint,
        knee: CGPoint,
        ankle: CGPoint
    ) -> Float {
        return calculateAngle(p1: hip, p2: knee, p3: ankle)
    }

    /// 세 점으로 각도 계산 (p2가 꼭짓점)
    private func calculateAngle(p1: CGPoint, p2: CGPoint, p3: CGPoint) -> Float {
        let v1 = CGVector(dx: p1.x - p2.x, dy: p1.y - p2.y)
        let v2 = CGVector(dx: p3.x - p2.x, dy: p3.y - p2.y)

        let dot = v1.dx * v2.dx + v1.dy * v2.dy
        let mag1 = sqrt(v1.dx * v1.dx + v1.dy * v1.dy)
        let mag2 = sqrt(v2.dx * v2.dx + v2.dy * v2.dy)

        if mag1 == 0 || mag2 == 0 {
            return 0
        }

        let cosAngle = dot / (mag1 * mag2)
        let angleRad = acos(max(-1, min(1, cosAngle)))
        return Float(angleRad * 180 / .pi)
    }

    /// 전체 정확도 계산
    private func calculateOverallAccuracy(angleDifferences: [String: Float]) -> Double {
        guard !angleDifferences.isEmpty else {
            return 1.0  // 비교할 게 없으면 완벽
        }

        let maxDiff: Float = 180.0  // 최대 각도 차이
        var totalAccuracy: Double = 0.0

        for (_, diff) in angleDifferences {
            let accuracy = max(0.0, 1.0 - Double(diff / maxDiff))
            totalAccuracy += accuracy
        }

        return totalAccuracy / Double(angleDifferences.count)
    }

    /// 그룹 이름 한국어 변환
    private func groupName(_ group: KeypointGroup) -> String {
        switch group {
        case .head:
            return "머리"
        case .shoulders:
            return "어깨"
        case .arms:
            return "팔"
        case .torso:
            return "몸통"
        case .legs:
            return "다리"
        }
    }
}
