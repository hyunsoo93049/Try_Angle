//
//  GateSystem.swift
//  v1.5 Gate System - 4단계 평가 시스템
//  작성일: 2025-12-05
//

import Foundation
import CoreGraphics

// MARK: - Gate 평가 결과
struct GateEvaluation {
    let gate1: GateResult  // 여백 균형
    let gate2: GateResult  // 프레이밍
    let gate3: GateResult  // 구도
    let gate4: GateResult  // 압축감

    var allPassed: Bool {
        return gate1.passed && gate2.passed && gate3.passed && gate4.passed
    }

    var passedCount: Int {
        return [gate1, gate2, gate3, gate4].filter { $0.passed }.count
    }

    var overallScore: CGFloat {
        let scores = [gate1.score, gate2.score, gate3.score, gate4.score]
        return scores.reduce(0, +) / CGFloat(scores.count)
    }

    var primaryFeedback: String {
        // 통과 못한 첫 번째 Gate의 피드백 반환
        if !gate1.passed { return gate1.feedback }
        if !gate2.passed { return gate2.feedback }
        if !gate3.passed { return gate3.feedback }
        if !gate4.passed { return gate4.feedback }
        return "✓ 완벽한 구도입니다!"
    }

    var allFeedbacks: [String] {
        return [gate1, gate2, gate3, gate4]
            .filter { !$0.passed }
            .map { $0.feedback }
    }
}

// MARK: - 개별 Gate 결과
struct GateResult {
    let name: String
    let score: CGFloat      // 0.0 ~ 1.0
    let threshold: CGFloat  // 통과 기준
    let passed: Bool
    let feedback: String

    init(name: String, score: CGFloat, threshold: CGFloat, feedback: String) {
        self.name = name
        self.score = score
        self.threshold = threshold
        self.passed = score >= threshold
        self.feedback = feedback
    }
}

// MARK: - Gate System
class GateSystem {

    // Gate 통과 기준
    private let thresholds = GateThresholds()

    struct GateThresholds {
        let marginBalance: CGFloat = 0.70     // Gate 1: 여백 균형 70%
        let framing: CGFloat = 0.65           // Gate 2: 프레이밍 65%
        let composition: CGFloat = 0.70       // Gate 3: 구도 70%
        let compression: CGFloat = 0.60       // Gate 4: 압축감 60%
    }

    private let marginAnalyzer = MarginAnalyzer()

    // MARK: - 전체 평가
    func evaluate(
        currentBBox: CGRect,
        referenceBBox: CGRect?,
        currentImageSize: CGSize,
        referenceImageSize: CGSize?,
        compressionIndex: CGFloat?,
        referenceCompressionIndex: CGFloat?
    ) -> GateEvaluation {

        // Gate 1: 여백 균형
        let gate1 = evaluateMarginBalance(
            bbox: currentBBox,
            imageSize: currentImageSize,
            referenceBBox: referenceBBox,
            referenceImageSize: referenceImageSize
        )

        // Gate 2: 프레이밍
        let gate2 = evaluateFraming(
            bbox: currentBBox,
            imageSize: currentImageSize,
            referenceBBox: referenceBBox,
            referenceImageSize: referenceImageSize
        )

        // Gate 3: 구도
        let gate3 = evaluateComposition(
            bbox: currentBBox,
            imageSize: currentImageSize
        )

        // Gate 4: 압축감
        let gate4 = evaluateCompression(
            currentIndex: compressionIndex,
            referenceIndex: referenceCompressionIndex
        )

        return GateEvaluation(gate1: gate1, gate2: gate2, gate3: gate3, gate4: gate4)
    }

    // MARK: - Gate 1: 여백 균형
    private func evaluateMarginBalance(
        bbox: CGRect,
        imageSize: CGSize,
        referenceBBox: CGRect?,
        referenceImageSize: CGSize?
    ) -> GateResult {

        if let refBBox = referenceBBox, let refSize = referenceImageSize {
            // 레퍼런스와 비교
            let comparison = marginAnalyzer.compareWithReference(
                current: bbox,
                reference: refBBox,
                currentImageSize: imageSize,
                referenceImageSize: refSize
            )

            let feedback = comparison.isMatched ? "여백 균형 일치" : comparison.adjustmentFeedback

            return GateResult(
                name: "여백 균형",
                score: comparison.overallMatch,
                threshold: thresholds.marginBalance,
                feedback: feedback
            )
        } else {
            // 절대 평가
            let margins = marginAnalyzer.analyze(bbox: bbox, imageSize: imageSize)
            let feedback = margins.movementDirection?.description ?? "여백 균형 양호"

            return GateResult(
                name: "여백 균형",
                score: margins.overallBalance,
                threshold: thresholds.marginBalance,
                feedback: feedback
            )
        }
    }

    // MARK: - Gate 2: 프레이밍
    private func evaluateFraming(
        bbox: CGRect,
        imageSize: CGSize,
        referenceBBox: CGRect?,
        referenceImageSize: CGSize?
    ) -> GateResult {

        // 인물 비중 계산 (bbox 면적 / 이미지 면적)
        let currentRatio = (bbox.width * bbox.height)
        let targetRatio: CGFloat

        if let refBBox = referenceBBox {
            targetRatio = refBBox.width * refBBox.height
        } else {
            // 기본 이상적 비중: 25% ~ 50%
            targetRatio = 0.35
        }

        // 비율 차이 계산
        let ratioDiff = abs(currentRatio - targetRatio)
        let score = max(0, 1.0 - (ratioDiff / 0.4))

        // 피드백 생성
        let feedback: String
        if currentRatio < targetRatio * 0.7 {
            feedback = "더 가까이 접근하세요"
        } else if currentRatio > targetRatio * 1.4 {
            feedback = "조금 뒤로 물러나세요"
        } else {
            feedback = "프레이밍 적절"
        }

        return GateResult(
            name: "프레이밍",
            score: score,
            threshold: thresholds.framing,
            feedback: feedback
        )
    }

    // MARK: - Gate 3: 구도
    private func evaluateComposition(
        bbox: CGRect,
        imageSize: CGSize
    ) -> GateResult {

        // 인물 중심점 계산
        let centerX = bbox.midX
        let centerY = bbox.midY

        // 3분할 선 위치 (정규화된 좌표 기준)
        let thirdLines: [CGFloat] = [1.0/3.0, 0.5, 2.0/3.0]

        // 가장 가까운 3분할 선과의 거리
        let minHorizontalDistance = thirdLines.map { abs(centerX - $0) }.min() ?? 0.5
        let minVerticalDistance = thirdLines.map { abs(centerY - $0) }.min() ?? 0.5

        // 점수 계산 (3분할 선에 가까울수록 높은 점수)
        let horizontalScore = max(0, 1.0 - (minHorizontalDistance / 0.2))
        let verticalScore = max(0, 1.0 - (minVerticalDistance / 0.2))
        let score = (horizontalScore + verticalScore) / 2.0

        // 피드백 생성
        let feedback: String
        if score >= thresholds.composition {
            feedback = "구도 양호"
        } else {
            // 어느 방향으로 이동해야 하는지
            let targetX = thirdLines.min(by: { abs($0 - centerX) < abs($1 - centerX) }) ?? 0.5
            let targetY = thirdLines.min(by: { abs($0 - centerY) < abs($1 - centerY) }) ?? 0.5

            var directions: [String] = []
            if centerX < targetX - 0.05 {
                directions.append("→ 오른쪽")
            } else if centerX > targetX + 0.05 {
                directions.append("← 왼쪽")
            }
            if centerY < targetY - 0.05 {
                directions.append("↓ 아래")
            } else if centerY > targetY + 0.05 {
                directions.append("↑ 위")
            }

            feedback = directions.isEmpty ? "3분할 선에 맞추세요" : directions.joined(separator: " | ")
        }

        return GateResult(
            name: "구도",
            score: score,
            threshold: thresholds.composition,
            feedback: feedback
        )
    }

    // MARK: - Gate 4: 압축감
    private func evaluateCompression(
        currentIndex: CGFloat?,
        referenceIndex: CGFloat?
    ) -> GateResult {

        guard let current = currentIndex else {
            // 깊이 정보 없음 - 패스
            return GateResult(
                name: "압축감",
                score: 1.0,
                threshold: thresholds.compression,
                feedback: "깊이 분석 대기 중"
            )
        }

        if let reference = referenceIndex {
            // 레퍼런스와 비교
            let diff = abs(current - reference)
            let score = max(0, 1.0 - (diff / 0.5))

            let feedback: String
            if diff < 0.15 {
                feedback = "압축감 일치"
            } else if current < reference {
                feedback = "줌인 또는 더 가까이"
            } else {
                feedback = "줌아웃 또는 더 멀리"
            }

            return GateResult(
                name: "압축감",
                score: score,
                threshold: thresholds.compression,
                feedback: feedback
            )
        } else {
            // 절대 평가 (0.3 ~ 0.7이 이상적)
            let idealRange: ClosedRange<CGFloat> = 0.3...0.7
            let score: CGFloat

            if idealRange.contains(current) {
                score = 1.0
            } else if current < idealRange.lowerBound {
                score = current / idealRange.lowerBound
            } else {
                score = (1.0 - current) / (1.0 - idealRange.upperBound)
            }

            let feedback: String
            if score >= thresholds.compression {
                feedback = "압축감 적절"
            } else if current < 0.3 {
                feedback = "배경이 너무 넓음 - 줌인 권장"
            } else {
                feedback = "배경이 너무 압축됨 - 줌아웃 권장"
            }

            return GateResult(
                name: "압축감",
                score: score,
                threshold: thresholds.compression,
                feedback: feedback
            )
        }
    }
}

// MARK: - Gate System 싱글톤
extension GateSystem {
    static let shared = GateSystem()
}
