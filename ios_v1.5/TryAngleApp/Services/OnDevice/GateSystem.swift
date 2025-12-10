//
//  GateSystem.swift
//  v1.5 통합 Gate System - 5단계 평가 시스템
//  작성일: 2025-12-05
//  수정일: 2025-12-07 (Phase 3 통합 + v7 피드백 문구 적용)
//
//  v7 피드백 개선 사항:
//  - 구체적인 수치 (걸음 수, 퍼센트)
//  - 친절한 설명 문구
//  - 샷 타입 + 조정 방법 명시
//  - 광각/망원 렌즈 표현
//

import Foundation
import CoreGraphics

// MARK: - Gate 평가 결과
struct GateEvaluation: Equatable {
    let gate0: GateResult  // 비율
    let gate1: GateResult  // 프레이밍 (샷타입 + 점유율)
    let gate2: GateResult  // 위치/구도 (여백 + 3분할)
    let gate3: GateResult  // 압축감
    let gate4: GateResult  // 포즈

    var allPassed: Bool {
        return gate0.passed && gate1.passed && gate2.passed && gate3.passed && gate4.passed
    }

    var passedCount: Int {
        return [gate0, gate1, gate2, gate3, gate4].filter { $0.passed }.count
    }

    var overallScore: CGFloat {
        let scores = [gate0.score, gate1.score, gate2.score, gate3.score, gate4.score]
        return scores.reduce(0, +) / CGFloat(scores.count)
    }

    /// 통과 못한 첫 번째 Gate의 피드백 반환 (우선순위 기반)
    var primaryFeedback: String {
        if !gate0.passed { return gate0.feedback }
        if !gate1.passed { return gate1.feedback }
        if !gate2.passed { return gate2.feedback }
        if !gate3.passed { return gate3.feedback }
        if !gate4.passed { return gate4.feedback }
        return "✓ 완벽한 구도입니다!"
    }

    var allFeedbacks: [String] {
        return [gate0, gate1, gate2, gate3, gate4]
            .filter { !$0.passed }
            .map { $0.feedback }
    }

    /// 현재 실패한 Gate 번호 (모두 통과 시 nil)
    var currentFailedGate: Int? {
        if !gate0.passed { return 0 }
        if !gate1.passed { return 1 }
        if !gate2.passed { return 2 }
        if !gate3.passed { return 3 }
        if !gate4.passed { return 4 }
        return nil
    }
}

// MARK: - 개별 Gate 결과
struct GateResult: Equatable {
    let name: String
    let score: CGFloat      // 0.0 ~ 1.0
    let threshold: CGFloat  // 통과 기준
    let passed: Bool
    let feedback: String
    let feedbackIcon: String  // 피드백 아이콘
    let category: String      // 피드백 카테고리

    init(name: String, score: CGFloat, threshold: CGFloat, feedback: String, icon: String = "📸", category: String = "general") {
        self.name = name
        self.score = score
        self.threshold = threshold
        self.passed = score >= threshold
        self.feedback = feedback
        self.feedbackIcon = icon
        self.category = category
    }
}

// MARK: - 샷 타입 (Phase 3에서 가져옴)
enum ShotTypeGate: Int, CaseIterable {
    case extremeCloseUp = 0  // 익스트림 클로즈업 (눈만)
    case closeUp = 1         // 클로즈업 (얼굴)
    case mediumCloseUp = 2   // 미디엄 클로즈업 (어깨)
    case mediumShot = 3      // 미디엄 샷 (허리)
    case americanShot = 4    // 아메리칸 샷 (무릎)
    case mediumFullShot = 5  // 미디엄 풀샷 (무릎 아래)
    case fullShot = 6        // 풀샷 (전신)
    case longShot = 7        // 롱샷 (전신 + 배경)

    var displayName: String {
        switch self {
        case .extremeCloseUp: return "익스트림 클로즈업"
        case .closeUp: return "클로즈업"
        case .mediumCloseUp: return "바스트샷"
        case .mediumShot: return "웨이스트샷"
        case .americanShot: return "니샷"
        case .mediumFullShot: return "미디엄 풀샷"
        case .fullShot: return "전신샷"
        case .longShot: return "롱샷"
        }
    }

    /// BBox 높이 비율로 샷 타입 추정 (fallback용)
    static func fromBBoxHeight(_ heightRatio: CGFloat) -> ShotTypeGate {
        // heightRatio: BBox 높이 / 이미지 높이
        if heightRatio > 0.9 { return .fullShot }
        if heightRatio > 0.75 { return .mediumFullShot }
        if heightRatio > 0.6 { return .americanShot }
        if heightRatio > 0.45 { return .mediumShot }
        if heightRatio > 0.3 { return .mediumCloseUp }
        if heightRatio > 0.15 { return .closeUp }
        return .extremeCloseUp
    }

    /// 🆕 키포인트 기반 샷타입 판별 (Python framing_analyzer.py 로직 이식)
    /// 가장 아래에 보이는 신체 부위로 샷타입 결정
    /// ⚠️ 핵심: confidence + 프레임 내 위치(y: 0.0~1.0) 둘 다 체크해야 함!
    static func fromKeypoints(_ keypoints: [PoseKeypoint], confidenceThreshold: Float = 0.5) -> ShotTypeGate {
        guard keypoints.count >= 17 else {
            return .mediumShot  // 키포인트 부족 시 기본값
        }

        // RTMPose 키포인트 인덱스 (COCO 17 + extended)
        // 0: nose, 5-6: shoulders, 7-8: elbows, 11-12: hips, 13-14: knees, 15-16: ankles

        /// 해당 부위가 "프레임 내에 보이는지" 체크
        /// - confidence > threshold
        /// - y좌표가 0.0 ~ 1.0 범위 내 (정규화된 좌표 기준)
        func isVisible(_ idx: Int) -> Bool {
            guard idx < keypoints.count else { return false }
            let kp = keypoints[idx]
            // confidence 체크 + 프레임 내 위치 체크 (y: 0.0 ~ 1.0)
            return kp.confidence > confidenceThreshold &&
                   kp.location.y >= 0.0 && kp.location.y <= 1.0 &&
                   kp.location.x >= 0.0 && kp.location.x <= 1.0
        }

        // 각 부위 가시성 체크 (confidence + 프레임 내 위치)
        let hasAnkles = isVisible(15) || isVisible(16)  // 발목
        let hasKnees = isVisible(13) || isVisible(14)   // 무릎
        let hasHips = isVisible(11) || isVisible(12)    // 골반
        let hasElbows = isVisible(7) || isVisible(8)    // 팔꿈치
        let hasShoulders = isVisible(5) || isVisible(6) // 어깨

        // 발 키포인트 (RTMPose 133 기준: 17~22)
        let hasFeet = keypoints.count > 22 && (17...22).contains(where: { isVisible($0) })

        // 얼굴 랜드마크 개수 (23~90) - 프레임 내 체크
        let faceKeypointCount = keypoints.count > 90 ? (23...90).filter { idx in
            guard idx < keypoints.count else { return false }
            let kp = keypoints[idx]
            return kp.confidence > 0.3 &&
                   kp.location.y >= 0.0 && kp.location.y <= 1.0
        }.count : 0

        // 디버그 로깅
        print("📸 샷타입 판별: ankles=\(hasAnkles), knees=\(hasKnees), hips=\(hasHips), elbows=\(hasElbows), shoulders=\(hasShoulders), feet=\(hasFeet), faceCount=\(faceKeypointCount)")

        // 샷타입 결정 (가장 아래에 보이는 부위 기준) - Python 로직과 동일
        if hasAnkles || hasFeet {
            return .fullShot           // 전신샷
        } else if hasKnees {
            return .americanShot       // 무릎샷 (니샷)
        } else if hasHips {
            if hasElbows {
                return .mediumShot     // 미디엄샷 (골반 + 팔꿈치)
            } else {
                return .mediumCloseUp  // 바스트샷 (골반만)
            }
        } else if hasElbows {
            return .mediumCloseUp      // 바스트샷 (팔꿈치까지)
        } else if hasShoulders {
            if faceKeypointCount > 50 {
                return .closeUp        // 클로즈업 (어깨 + 얼굴 상세)
            } else {
                return .mediumCloseUp  // 바스트샷 (어깨만)
            }
        } else {
            return .extremeCloseUp     // 얼굴만
        }
    }

    /// 두 샷 타입 간 거리 (0~7)
    func distance(to other: ShotTypeGate) -> Int {
        return abs(self.rawValue - other.rawValue)
    }
}

// MARK: - Gate System
class GateSystem {

    // Gate 통과 기준
    private let thresholds = GateThresholds()

    struct GateThresholds {
        let aspectRatio: CGFloat = 1.0        // Gate 0: 비율 (완전 일치 필요)
        let framing: CGFloat = 0.75           // Gate 1: 프레이밍 75% (🔧 상향)
        let position: CGFloat = 0.80          // Gate 2: 위치/구도 80% (🔧 조정)
        let compression: CGFloat = 0.70       // Gate 3: 압축감 70% (🔧 상향)
        let pose: CGFloat = 0.70              // Gate 4: 포즈 70% (🔧 상향)
    }

    private let marginAnalyzer = MarginAnalyzer()

    // MARK: - 전체 평가
    func evaluate(
        currentBBox: CGRect,
        referenceBBox: CGRect?,
        currentImageSize: CGSize,
        referenceImageSize: CGSize?,
        compressionIndex: CGFloat?,
        referenceCompressionIndex: CGFloat?,
        currentAspectRatio: CameraAspectRatio = .ratio4_3,
        referenceAspectRatio: CameraAspectRatio = .ratio4_3,
        poseComparison: PoseComparisonResult? = nil,
        isFrontCamera: Bool = false,
        currentKeypoints: [PoseKeypoint]? = nil,      // 🆕 현재 프레임 키포인트
        referenceKeypoints: [PoseKeypoint]? = nil,    // 🆕 레퍼런스 키포인트
        currentFocalLength: FocalLengthInfo? = nil,   // 🆕 현재 35mm 환산 초점거리
        referenceFocalLength: FocalLengthInfo? = nil  // 🆕 레퍼런스 35mm 환산 초점거리
    ) -> GateEvaluation {

        // 🆕 현재 프레임에 인물이 있는지 체크
        // BBox가 너무 작거나 (5% 미만) 없으면 인물 미검출로 판단
        let minValidSize: CGFloat = 0.05  // 최소 5% 이상 차지해야 유효
        let hasCurrentPerson = currentBBox.width > minValidSize && currentBBox.height > minValidSize

        // Gate 0: 비율 체크 (최우선) - 인물 없어도 체크 가능
        let gate0 = evaluateAspectRatio(
            current: currentAspectRatio,
            reference: referenceAspectRatio
        )

        // 🆕 인물이 없으면 Gate 1~4는 모두 "인물 미검출" 피드백
        guard hasCurrentPerson else {
            let noPersonResult = GateResult(
                name: "인물 미검출",
                score: 0.0,
                threshold: 0.5,
                feedback: "인물이 검출되지 않습니다. 프레임 안에 들어오세요",
                icon: "👤",
                category: "no_person"
            )
            return GateEvaluation(
                gate0: gate0,
                gate1: noPersonResult,
                gate2: noPersonResult,
                gate3: noPersonResult,
                gate4: noPersonResult
            )
        }

        // Gate 1: 프레이밍 (샷타입 + 점유율) - 🆕 v6 키포인트 기반 샷타입
        let gate1 = evaluateFraming(
            bbox: currentBBox,
            imageSize: currentImageSize,
            referenceBBox: referenceBBox,
            referenceImageSize: referenceImageSize,
            isFrontCamera: isFrontCamera,
            currentKeypoints: currentKeypoints,      // 🆕 v6: 현재 프레임 키포인트
            referenceKeypoints: referenceKeypoints   // 🆕 v6: 레퍼런스 키포인트
        )

        // Gate 2: 위치/구도 (여백 균형 + 3분할)
        let gate2 = evaluatePosition(
            bbox: currentBBox,
            imageSize: currentImageSize,
            referenceBBox: referenceBBox,
            referenceImageSize: referenceImageSize,
            isFrontCamera: isFrontCamera
        )

        // Gate 3: 압축감 (35mm 환산 초점거리 기반)
        let gate3 = evaluateCompression(
            currentIndex: compressionIndex,
            referenceIndex: referenceCompressionIndex,
            currentFocal: currentFocalLength,
            referenceFocal: referenceFocalLength
        )

        // Gate 4: 포즈
        let gate4 = evaluatePose(
            poseComparison: poseComparison,
            isFrontCamera: isFrontCamera,
            hasCurrentPerson: hasCurrentPerson
        )

        // 🔧 DEBUG: 각 Gate 점수 상세 로깅
        print("📊 Gate 상세 점수:")
        print("   G0 비율: \(String(format: "%.0f%%", gate0.score * 100)) (임계값: 100%) → \(gate0.passed ? "✅" : "❌")")
        print("   G1 프레이밍: \(String(format: "%.0f%%", gate1.score * 100)) (임계값: 75%) → \(gate1.passed ? "✅" : "❌")")
        print("   G2 위치: \(String(format: "%.0f%%", gate2.score * 100)) (임계값: 80%) → \(gate2.passed ? "✅" : "❌")")
        print("   G3 압축감: \(String(format: "%.0f%%", gate3.score * 100)) (임계값: 70%) → \(gate3.passed ? "✅" : "❌")")
        print("   G4 포즈: \(String(format: "%.0f%%", gate4.score * 100)) (임계값: 70%) → \(gate4.passed ? "✅" : "❌")")
        print("   현재BBox: \(String(format: "(%.2f,%.2f) %.2fx%.2f", currentBBox.minX, currentBBox.minY, currentBBox.width, currentBBox.height))")

        return GateEvaluation(gate0: gate0, gate1: gate1, gate2: gate2, gate3: gate3, gate4: gate4)
    }

    // MARK: - Gate 0: 비율 체크
    private func evaluateAspectRatio(
        current: CameraAspectRatio,
        reference: CameraAspectRatio
    ) -> GateResult {
        let matched = current == reference
        let score: CGFloat = matched ? 1.0 : 0.0

        let feedback: String
        if matched {
            feedback = "비율 일치"
        } else {
            feedback = "카메라 비율을 \(reference.displayName)로 변경하세요"
        }

        return GateResult(
            name: "비율",
            score: score,
            threshold: thresholds.aspectRatio,
            feedback: feedback,
            icon: "📐",
            category: "aspect_ratio"
        )
    }

    // MARK: - Gate 1: 프레이밍 (샷타입 + 점유율) - v7 스타일 + v6 키포인트 기반
    private func evaluateFraming(
        bbox: CGRect,
        imageSize: CGSize,
        referenceBBox: CGRect?,
        referenceImageSize: CGSize?,
        isFrontCamera: Bool,
        currentKeypoints: [PoseKeypoint]? = nil,      // 🆕 v6: 키포인트 기반 샷타입
        referenceKeypoints: [PoseKeypoint]? = nil     // 🆕 v6: 레퍼런스 키포인트
    ) -> GateResult {

        // 🆕 v6: 키포인트 기반 샷타입 우선 사용 (Python framing_analyzer.py 로직)
        let currentShotType: ShotTypeGate
        if let keypoints = currentKeypoints, keypoints.count >= 17 {
            currentShotType = ShotTypeGate.fromKeypoints(keypoints)
        } else {
            // fallback: BBox 높이 기반
            let currentHeightRatio = bbox.height
            currentShotType = ShotTypeGate.fromBBoxHeight(currentHeightRatio)
        }

        // 현재 점유율 (BBox 면적 / 이미지 면적)
        let currentCoverage = bbox.width * bbox.height

        // 🆕 프레임 가장자리 체크 (너무 가까워서 잘린 상태 감지)
        // BBox가 프레임 가장자리에 닿으면 인물이 프레임 밖으로 나갔을 가능성 높음
        let edgeThreshold: CGFloat = 0.02  // 2% 이내면 가장자리
        let isAtTopEdge = bbox.minY < edgeThreshold
        let isAtBottomEdge = bbox.maxY > (1.0 - edgeThreshold)
        let isAtLeftEdge = bbox.minX < edgeThreshold
        let isAtRightEdge = bbox.maxX > (1.0 - edgeThreshold)
        let _ = isAtTopEdge || isAtBottomEdge || isAtLeftEdge || isAtRightEdge

        // 신체가 가장자리 여러 곳에 닿아있으면 "너무 가까움" 판단
        let edgeCount = [isAtTopEdge, isAtBottomEdge, isAtLeftEdge, isAtRightEdge].filter { $0 }.count
        let isTooCloseAndCropped = edgeCount >= 2  // 2개 이상의 가장자리에 닿음

        var score: CGFloat = 1.0
        var feedback = "인물 크기가 프레임 대비 적절합니다"

        if let refBBox = referenceBBox {
            // 🆕 v6: 레퍼런스 샷타입도 키포인트 기반 우선
            let refShotType: ShotTypeGate
            if let keypoints = referenceKeypoints, keypoints.count >= 17 {
                refShotType = ShotTypeGate.fromKeypoints(keypoints)
            } else {
                // fallback: BBox 높이 기반
                let refHeightRatio = refBBox.height
                refShotType = ShotTypeGate.fromBBoxHeight(refHeightRatio)
            }

            // ============================================
            // 🔧 v8: Gate 1은 샷타입만 체크! (점유율은 Gate 2로)
            // ============================================
            // 샷 타입 거리 (0~7)
            let shotTypeDist = currentShotType.distance(to: refShotType)

            // 🔧 점수 = 샷타입만으로 계산 (점유율 제외!)
            // 거리 1 = 인접 샷타입 (예: 바스트↔미디엄) → 허용
            // 거리 2+ = 샷타입 차이가 큼 → 조정 필요
            if shotTypeDist == 0 {
                score = 1.0  // 완벽 일치
            } else if shotTypeDist == 1 {
                score = 0.85  // 인접 샷타입 → 통과 (세부 조정은 Gate 2에서)
            } else {
                score = max(0.3, 1.0 - CGFloat(shotTypeDist) * 0.2)
            }

            // 🆕 너무 가까워서 잘린 경우 특별 처리
            if isTooCloseAndCropped {
                score = max(0.3, score - 0.2)  // 🔧 감점 완화 (0.3 → 0.2)

                var croppedParts: [String] = []
                if isAtTopEdge { croppedParts.append("상단") }
                if isAtBottomEdge { croppedParts.append("하단") }
                if isAtLeftEdge { croppedParts.append("좌측") }
                if isAtRightEdge { croppedParts.append("우측") }
                let croppedDesc = croppedParts.joined(separator: "/")

                feedback = isFrontCamera
                    ? "너무 가까워요! \(croppedDesc)이 잘렸어요. 뒤로 물러나세요"
                    : "피사체가 너무 가까워요! \(croppedDesc)이 잘렸어요. 뒤로 가세요"
            }
            // 🔧 샷타입 거리 2 이상만 피드백 (1은 허용)
            else if shotTypeDist >= 2 {
                let steps = max(1, shotTypeDist)

                if currentShotType.rawValue > refShotType.rawValue {
                    // 현재가 더 넓음 (전신) → 가까이
                    feedback = isFrontCamera
                        ? "\(currentShotType.displayName) → \(refShotType.displayName). 약 \(steps)걸음 앞으로"
                        : "\(currentShotType.displayName) → \(refShotType.displayName). 약 \(steps)걸음 가까이"
                } else {
                    // 현재가 더 좁음 (클로즈업) → 뒤로
                    feedback = isFrontCamera
                        ? "\(currentShotType.displayName) → \(refShotType.displayName). 약 \(steps)걸음 뒤로"
                        : "\(currentShotType.displayName) → \(refShotType.displayName). 약 \(steps)걸음 뒤로"
                }
            }
            // 🔧 샷타입 OK (거리 0~1) → 세부 조정은 Gate 2에서 처리
            else {
                feedback = "✓ 샷타입 OK (\(currentShotType.displayName))"
            }
        } else {
            // 절대 평가: 이상적 점유율 25%~50%
            if currentCoverage < 0.20 {
                score = currentCoverage / 0.20
                feedback = isFrontCamera
                    ? "인물이 너무 작아요. 앞으로 다가오세요"
                    : "인물이 너무 작아요. 카메라를 더 가까이 하세요"
            } else if currentCoverage > 0.55 {
                score = max(0, 1.0 - (currentCoverage - 0.55) / 0.3)
                feedback = isFrontCamera
                    ? "인물이 화면을 너무 차지해요. 뒤로 물러나세요"
                    : "인물이 화면을 너무 차지해요. 카메라를 뒤로 하세요"
            }
        }

        return GateResult(
            name: "프레이밍",
            score: score,
            threshold: thresholds.framing,
            feedback: feedback,
            icon: "📸",
            category: "framing"
        )
    }

    // MARK: - Gate 2: 위치/구도 (v6 improved_margin_analyzer.py 전체 이식)
    private func evaluatePosition(
        bbox: CGRect,
        imageSize: CGSize,
        referenceBBox: CGRect?,
        referenceImageSize: CGSize?,
        isFrontCamera: Bool
    ) -> GateResult {

        // 현재 여백 분석
        let curMargins = marginAnalyzer.analyze(bbox: bbox, imageSize: imageSize)

        var score: CGFloat = 1.0
        var feedback = "인물 위치가 레퍼런스와 잘 맞습니다"
        var feedbackParts: [String] = []

        // 🆕 v6: 프레임 밖 경고 우선 표시
        if let warning = curMargins.outOfFrameWarning {
            feedbackParts.append(warning)
        }

        if let refBBox = referenceBBox, let refSize = referenceImageSize {
            // 레퍼런스와 비교
            let refMargins = marginAnalyzer.analyze(bbox: refBBox, imageSize: refSize)

            // 🆕 v6: 좌우 균형 분석 (Python _analyze_horizontal_balance)
            let horizontalResult = analyzeHorizontalBalance(
                curMargins: curMargins, refMargins: refMargins, isFrontCamera: isFrontCamera
            )
            score = horizontalResult.score

            if let horizontalFeedback = horizontalResult.feedback {
                feedbackParts.append(horizontalFeedback)
            }

            // 🆕 v6: 상하 균형 분석 + 틸트 (Python _analyze_vertical_balance)
            let verticalResult = analyzeVerticalBalance(
                curMargins: curMargins, refMargins: refMargins, isFrontCamera: isFrontCamera
            )
            score = (score + verticalResult.score) / 2.0

            if let verticalFeedback = verticalResult.feedback {
                feedbackParts.append(verticalFeedback)
            }

            // 🆕 v6: 하단 특별 분석 (Python _analyze_bottom_special)
            let bottomResult = analyzeBottomSpecial(
                curMargins: curMargins, refMargins: refMargins
            )
            score = score * 0.7 + bottomResult.score * 0.3  // 하단 30% 가중치

            if let bottomFeedback = bottomResult.feedback {
                feedbackParts.append(bottomFeedback)
            }

        } else {
            // 절대 평가: 3분할 선 기준
            let centerX = bbox.midX
            let centerY = bbox.midY
            let thirdLines: [CGFloat] = [1.0/3.0, 0.5, 2.0/3.0]

            let minHorizontalDistance = thirdLines.map { abs(centerX - $0) }.min() ?? 0.5
            let minVerticalDistance = thirdLines.map { abs(centerY - $0) }.min() ?? 0.5

            let horizontalScore = max(0, 1.0 - (minHorizontalDistance / 0.2))
            let verticalScore = max(0, 1.0 - (minVerticalDistance / 0.2))
            score = (horizontalScore + verticalScore) / 2.0

            if score < thresholds.position {
                let targetX = thirdLines.min(by: { abs($0 - centerX) < abs($1 - centerX) }) ?? 0.5
                let targetY = thirdLines.min(by: { abs($0 - centerY) < abs($1 - centerY) }) ?? 0.5

                if centerX < targetX - 0.05 {
                    feedbackParts.append(isFrontCamera
                        ? "피사체를 화면의 왼쪽으로 이동하세요"
                        : "피사체를 화면의 오른쪽으로 이동하세요")
                } else if centerX > targetX + 0.05 {
                    feedbackParts.append(isFrontCamera
                        ? "피사체를 화면의 오른쪽으로 이동하세요"
                        : "피사체를 화면의 왼쪽으로 이동하세요")
                }

                if centerY < targetY - 0.05 {
                    feedbackParts.append("피사체를 화면의 아래쪽으로 이동하세요")
                } else if centerY > targetY + 0.05 {
                    feedbackParts.append("피사체를 화면의 위쪽으로 이동하세요")
                }
            }
        }

        if !feedbackParts.isEmpty {
            feedback = feedbackParts.joined(separator: "\n")
        }

        return GateResult(
            name: "위치",
            score: score,
            threshold: thresholds.position,
            feedback: feedback,
            icon: "↔️",
            category: "position"
        )
    }

    // 🆕 v6: 좌우 균형 분석 (Python _analyze_horizontal_balance 이식)
    private struct BalanceAnalysisResult {
        let score: CGFloat
        let feedback: String?
    }

    private func analyzeHorizontalBalance(
        curMargins: MarginAnalysisResult,
        refMargins: MarginAnalysisResult,
        isFrontCamera: Bool
    ) -> BalanceAnalysisResult {

        // Python: curr_balance = curr['left'] - curr['right']
        let currBalance = curMargins.leftRatio - curMargins.rightRatio
        let refBalance = refMargins.leftRatio - refMargins.rightRatio

        // Python: center_shift = curr_balance - ref_balance
        let centerShift = currBalance - refBalance

        // 임계값 (Python thresholds)
        let perfect: CGFloat = 0.05
        let good: CGFloat = 0.10
        let needsAdjustment: CGFloat = 0.15

        // 점수 계산
        let score: CGFloat
        if abs(centerShift) < perfect {
            score = 0.95
        } else if abs(centerShift) < good {
            score = 0.85
        } else if abs(centerShift) < needsAdjustment {
            score = 0.70
        } else {
            score = max(0.50, 0.85 - abs(centerShift))
        }

        // 피드백 생성 (Python: camera_action + person_action)
        var feedback: String? = nil
        if abs(centerShift) > good {
            let percent = min(50, Int(abs(centerShift) * 100))
            let steps = toSteps(percent: CGFloat(percent))  // 🆕 걸음수 변환

            if centerShift > 0 {
                // 현재가 더 왼쪽 치우침 → 오른쪽으로 이동
                feedback = isFrontCamera
                    ? "오른쪽으로 \(steps) 이동 (\(percent)%)"
                    : "왼쪽으로 \(steps) 이동 (\(percent)%)"
            } else {
                // 현재가 더 오른쪽 치우침 → 왼쪽으로 이동
                feedback = isFrontCamera
                    ? "왼쪽으로 \(steps) 이동 (\(percent)%)"
                    : "오른쪽으로 \(steps) 이동 (\(percent)%)"
            }
        }

        return BalanceAnalysisResult(score: score, feedback: feedback)
    }

    // 🆕 v6: 상하 균형 분석 + 틸트 (Python _analyze_vertical_balance 이식)
    private func analyzeVerticalBalance(
        curMargins: MarginAnalysisResult,
        refMargins: MarginAnalysisResult,
        isFrontCamera: Bool
    ) -> BalanceAnalysisResult {

        // Python: 인물의 절대 위치 (0=상단, 1=하단)
        let currPosition = curMargins.personVerticalPosition
        let refPosition = refMargins.personVerticalPosition

        // Python: position_diff = curr_position - ref_position
        let positionDiff = currPosition - refPosition

        // 임계값
        let perfect: CGFloat = 0.05
        let good: CGFloat = 0.10
        let needsAdjustment: CGFloat = 0.15

        // 점수 계산
        let score: CGFloat
        if abs(positionDiff) < perfect {
            score = 0.95
        } else if abs(positionDiff) < good {
            score = 0.85
        } else if abs(positionDiff) < needsAdjustment {
            score = 0.70
        } else {
            score = max(0.50, 0.85 - abs(positionDiff))
        }

        // 피드백 생성 (틸트 + 인물 행동)
        var feedback: String? = nil
        if abs(positionDiff) > good {
            // Python: _to_tilt_angle
            let tiltAngle = toTiltAngle(percent: abs(positionDiff) * 100)

            if positionDiff > 0 {
                // 현재가 더 아래에 위치 (상단 여백 많음) - Python 로직
                if curMargins.isHighAngle {
                    // 하이앵글 + 인물 아래 = 카메라 낮추고 평행하게
                    // Python: camera_action + person_action
                    feedback = isFrontCamera
                        ? "카메라를 낮추고 \(tiltAngle)° 평행하게 (또는 프레임 아래로 이동)"
                        : "카메라를 낮추고 \(tiltAngle)° 평행하게"
                } else {
                    // 평행 앵글 + 인물 아래 = 틸트 다운
                    // Python: person_action = "앉거나 자세를 낮추기"
                    feedback = isFrontCamera
                        ? "카메라를 \(tiltAngle)° 아래로 틸트 (또는 자세를 낮추기)"
                        : "카메라를 \(tiltAngle)° 아래로 틸트"
                }
            } else {
                // 현재가 더 위에 위치 (하단 여백 많음)
                // Python: person_action = "일어서거나 자세를 높이기"
                feedback = isFrontCamera
                    ? "카메라를 \(tiltAngle)° 위로 틸트 (또는 자세를 높이기)"
                    : "카메라를 \(tiltAngle)° 위로 틸트"
            }
        }

        return BalanceAnalysisResult(score: score, feedback: feedback)
    }

    // 🆕 v6: 하단 특별 분석 (Python _analyze_bottom_special 이식)
    private func analyzeBottomSpecial(
        curMargins: MarginAnalysisResult,
        refMargins: MarginAnalysisResult
    ) -> BalanceAnalysisResult {

        let currBottom = curMargins.bottomRatio
        let refBottom = refMargins.bottomRatio

        // Python: 하단 여백 차이
        let diff = abs(currBottom - refBottom)

        // 점수 계산
        let score: CGFloat
        if diff < 0.05 {
            score = 0.95
        } else if diff < 0.10 {
            score = 0.85
        } else if diff < 0.15 {
            score = 0.75
        } else {
            score = max(0.60, 0.90 - diff)
        }

        // 특별 케이스 피드백 (Python: table_heavy, too_much_bottom 등)
        var feedback: String? = nil

        // Python: table_heavy = curr_bottom < -0.1 (하단 10% 이상 잘림)
        if currBottom < -0.1 {
            feedback = "하단이 잘렸어요. 카메라를 위로 들거나 뒤로 물러나세요"
        }
        // Python: too_much_bottom = curr_bottom > ref_bottom + 0.15
        else if currBottom > refBottom + 0.15 {
            feedback = "하단 여백이 너무 많아요. 카메라를 아래로 내리세요"
        }
        // Python: too_little_bottom = curr_bottom < ref_bottom - 0.15
        else if currBottom < refBottom - 0.15 {
            feedback = "하단 여백이 부족해요. 카메라를 위로 올리세요"
        }

        return BalanceAnalysisResult(score: score, feedback: feedback)
    }

    // 🆕 v6: 퍼센트를 틸트 각도로 변환 (Python _to_tilt_angle)
    private func toTiltAngle(percent: CGFloat) -> Int {
        if percent < 5 {
            return 2
        } else if percent < 10 {
            return 5
        } else if percent < 15 {
            return 8
        } else if percent < 20 {
            return 10
        } else {
            return min(15, Int(percent * 0.5))
        }
    }

    // 🆕 v6: 퍼센트를 걸음수로 변환 (Python _to_steps 이식)
    private func toSteps(percent: CGFloat) -> String {
        if percent < 5 {
            return "아주 조금"
        } else if percent < 10 {
            return "반 걸음"
        } else if percent < 20 {
            return "한 걸음"
        } else if percent < 30 {
            return "두 걸음"
        } else if percent < 40 {
            return "세 걸음"
        } else {
            return "네 걸음 이상"
        }
    }

    // MARK: - Gate 3: 압축감 - 35mm 환산 초점거리 기반
    private func evaluateCompression(
        currentIndex: CGFloat?,
        referenceIndex: CGFloat?,
        currentFocal: FocalLengthInfo? = nil,
        referenceFocal: FocalLengthInfo? = nil
    ) -> GateResult {

        // 🆕 35mm 환산 초점거리 우선 사용
        if let currentFL = currentFocal {
            return evaluateCompressionByFocalLength(
                current: currentFL,
                reference: referenceFocal
            )
        }

        // Fallback: 기존 compressionIndex 방식
        guard let current = currentIndex else {
            return GateResult(
                name: "압축감",
                score: 0.0,
                threshold: thresholds.compression,
                feedback: "깊이 정보를 분석 중입니다...",
                icon: "🔭",
                category: "compression"
            )
        }

        // 렌즈 타입 판별 함수 (레거시)
        func describeLensType(_ value: CGFloat) -> (name: String, type: String) {
            if value < 0.3 {
                return ("광각렌즈", "wide")
            } else if value < 0.45 {
                return ("준광각", "semi-wide")
            } else if value < 0.6 {
                return ("표준렌즈", "normal")
            } else if value < 0.75 {
                return ("중망원", "medium-tele")
            } else {
                return ("망원렌즈", "telephoto")
            }
        }

        let currentLens = describeLensType(current)
        var score: CGFloat = 1.0
        var feedback = "압축감이 레퍼런스와 유사합니다 (\(currentLens.name))"

        if let reference = referenceIndex {
            let referenceLens = describeLensType(reference)
            let diff = abs(current - reference)
            let diffPercent = Int(diff * 100)

            score = max(0, 1.0 - (diff / 0.5))

            if diff >= 0.15 {
                if current < reference {
                    feedback = "배경 압축이 부족해요. 줌인하거나 \(max(1, diffPercent / 10))걸음 가까이 가세요 (현재: \(currentLens.name) → 목표: \(referenceLens.name))"
                } else {
                    feedback = "배경이 너무 압축되어요. 줌아웃하거나 \(max(1, diffPercent / 10))걸음 뒤로 가세요 (현재: \(currentLens.name) → 목표: \(referenceLens.name))"
                }
            }
        } else {
            let idealRange: ClosedRange<CGFloat> = 0.3...0.7

            if idealRange.contains(current) {
                score = 1.0
                feedback = "적절한 압축감입니다 (\(currentLens.name))"
            } else if current < idealRange.lowerBound {
                score = current / idealRange.lowerBound
                feedback = "광각렌즈 효과가 너무 강해요. 줌인하거나 가까이 가세요"
            } else {
                score = (1.0 - current) / (1.0 - idealRange.upperBound)
                feedback = "망원렌즈 효과가 너무 강해요. 줌아웃하거나 뒤로 가세요"
            }
        }

        return GateResult(
            name: "압축감",
            score: score,
            threshold: thresholds.compression,
            feedback: feedback,
            icon: "🔭",
            category: "compression"
        )
    }

    // 🆕 35mm 환산 초점거리 기반 압축감 평가
    private func evaluateCompressionByFocalLength(
        current: FocalLengthInfo,
        reference: FocalLengthInfo?
    ) -> GateResult {

        let currentMM = current.focalLength35mm
        let currentLens = current.lensType

        var score: CGFloat = 1.0
        var feedback = "\(currentMM)mm \(currentLens.displayName)으로 촬영 중"

        // 🔧 v8: 레퍼런스 초점거리가 없으면 기본값 50mm 사용 (스마트폰 표준)
        // ⚠️ EXIF가 없어도 상대 비교 가능하도록!
        let refMM: Int
        let isEstimated: Bool

        if let ref = reference {
            refMM = ref.focalLength35mm
            let _ = ref.lensType  // lensType은 로깅용으로만 사용
            isEstimated = ref.source == .fallback || ref.confidence < 0.5
        } else {
            // 🆕 레퍼런스 EXIF 없음 → 50mm (표준 렌즈) 가정
            refMM = 50
            isEstimated = true
            print("📐 [압축감] 레퍼런스 EXIF 없음 → 기본값 50mm 사용")
        }

        let diff = abs(currentMM - refMM)

        // 점수 계산: 초점거리 차이에 따라 감점
        // 🔧 v8: 더 민감하게 (5mm 차이마다 10% 감점)
        score = max(0, 1.0 - CGFloat(diff) / 50.0)

        // 🔧 v8: 임계값 10mm로 낮춤 (더 민감하게 체크)
        if diff > 10 {
            let targetZoom = CGFloat(refMM) / CGFloat(FocalLengthEstimator.iPhoneBaseFocalLength)
            let zoomText = String(format: "%.1fx", targetZoom)

            if currentMM < refMM {
                // 현재가 더 광각 → 줌인 필요
                feedback = "📐 \(zoomText)로 줌인 (현재 \(currentMM)mm → \(refMM)mm)"
            } else {
                // 현재가 더 망원 → 줌아웃 필요
                feedback = "📐 \(zoomText)로 줌아웃 (현재 \(currentMM)mm → \(refMM)mm)"
            }

            if isEstimated {
                feedback += " [추정]"
            }
        } else {
            // 차이가 적음 → 유사함
            feedback = "✓ 압축감 OK (\(currentMM)mm)"
        }

        // 🆕 항상 디버그 출력
        print("📐 [압축감] 현재:\(currentMM)mm vs 목표:\(refMM)mm → 차이:\(diff)mm, 점수:\(String(format: "%.2f", score)), 통과:\(score >= thresholds.compression)")

        return GateResult(
            name: "압축감",
            score: score,
            threshold: thresholds.compression,
            feedback: feedback,
            icon: "🔭",
            category: "compression"
        )
    }

    // MARK: - Gate 4: 포즈
    private func evaluatePose(
        poseComparison: PoseComparisonResult?,
        isFrontCamera: Bool,
        hasCurrentPerson: Bool = true  // 🆕 현재 프레임에 인물 있는지
    ) -> GateResult {

        // 🆕 현재 프레임에 인물이 없으면 우선 피드백
        guard hasCurrentPerson else {
            return GateResult(
                name: "포즈",
                score: 0.0,
                threshold: thresholds.pose,
                feedback: "인물이 검출되지 않습니다. 프레임 안에 들어오세요",
                icon: "🤸",
                category: "pose"
            )
        }

        guard let pose = poseComparison else {
            // 🔧 수정: 포즈 비교 결과 없음 - 통과가 아닌 대기 상태
            return GateResult(
                name: "포즈",
                score: 0.0,  // 🔧 1.0 → 0.0 (미통과)
                threshold: thresholds.pose,
                feedback: "포즈를 분석 중입니다...",
                icon: "🤸",
                category: "pose"
            )
        }

        // 전체 정확도를 점수로 사용
        let score = CGFloat(pose.overallAccuracy)

        // 각도 차이가 큰 부위 찾기
        let angleDiffThreshold: Float = 15.0
        var feedbackParts: [String] = []

        // 우선순위 순서로 체크
        let priorityParts = ["shoulder_tilt", "face", "left_arm", "right_arm", "left_leg", "right_leg"]

        for part in priorityParts {
            if let diff = pose.angleDifferences[part], abs(diff) > angleDiffThreshold {
                // angleDirections에서 구체적인 메시지 가져오기
                if let direction = pose.angleDirections[part] {
                    feedbackParts.append(direction)
                } else {
                    // fallback
                    switch part {
                    case "shoulder_tilt":
                        feedbackParts.append("몸 기울기 조정")
                    case "face":
                        feedbackParts.append("고개 방향 조정")
                    case "left_arm":
                        feedbackParts.append("왼팔 각도 조정")
                    case "right_arm":
                        feedbackParts.append("오른팔 각도 조정")
                    case "left_leg":
                        feedbackParts.append("왼다리 각도 조정")
                    case "right_leg":
                        feedbackParts.append("오른다리 각도 조정")
                    default:
                        break
                    }
                }

                // 최대 2개만 표시
                if feedbackParts.count >= 2 { break }
            }
        }

        // 🔧 v6: missingGroups "잘렸어요" 피드백 제거
        // 상반신샷에서 다리가 안 보이는 건 정상이므로, 샷타입과 무관하게 표시하면 혼란스러움
        // Python v6에서도 이런 피드백은 없음 - 샷타입 분석에서 처리
        // (필요시 currentShotType을 파라미터로 받아 필터링 가능)

        let feedback = feedbackParts.isEmpty ? "포즈 일치" : feedbackParts.joined(separator: ", ")

        return GateResult(
            name: "포즈",
            score: score,
            threshold: thresholds.pose,
            feedback: feedback,
            icon: "🤸",
            category: "pose"
        )
    }
}

// MARK: - Gate System 싱글톤
extension GateSystem {
    static let shared = GateSystem()
}
