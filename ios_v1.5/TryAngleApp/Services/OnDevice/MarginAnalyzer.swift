//
//  MarginAnalyzer.swift
//  v1.5 개선된 여백 분석기
//  작성일: 2025-12-05
//

import Foundation
import CoreGraphics
import UIKit

// MARK: - 여백 분석 결과
struct MarginAnalysisResult {
    // 절대 여백 (픽셀)
    let left: CGFloat
    let right: CGFloat
    let top: CGFloat
    let bottom: CGFloat

    // 비율 (0.0 ~ 1.0)
    let leftRatio: CGFloat
    let rightRatio: CGFloat
    let topRatio: CGFloat
    let bottomRatio: CGFloat

    // 균형 점수
    let horizontalBalance: CGFloat  // 좌우 균형 (1.0 = 완벽)
    let verticalBalance: CGFloat    // 상하 균형 (1.0 = 완벽)
    let overallBalance: CGFloat     // 전체 균형 점수

    // 피드백
    let horizontalFeedback: String?
    let verticalFeedback: String?
    let movementDirection: MovementDirection?
}

// MARK: - 이동 방향
struct MovementDirection {
    let horizontal: HorizontalDirection?
    let vertical: VerticalDirection?
    let amount: CGFloat  // 이동량 (0.0 ~ 1.0)

    enum HorizontalDirection: String {
        case left = "왼쪽"
        case right = "오른쪽"

        var arrow: String {
            switch self {
            case .left: return "←"
            case .right: return "→"
            }
        }
    }

    enum VerticalDirection: String {
        case up = "위"
        case down = "아래"

        var arrow: String {
            switch self {
            case .up: return "↑"
            case .down: return "↓"
            }
        }
    }

    var primaryArrow: String {
        if let h = horizontal, let v = vertical {
            // 더 큰 차이가 나는 방향 우선
            return amount > 0.1 ? h.arrow : v.arrow
        }
        return horizontal?.arrow ?? vertical?.arrow ?? ""
    }

    var description: String {
        var parts: [String] = []
        if let h = horizontal {
            parts.append("\(h.arrow) \(h.rawValue)")
        }
        if let v = vertical {
            parts.append("\(v.arrow) \(v.rawValue)")
        }
        return parts.joined(separator: " | ")
    }
}

// MARK: - 여백 분석기
class MarginAnalyzer {

    // 설정 상수
    private let minMarginRatio: CGFloat = 0.03      // 최소 여백 비율 (3%)
    private let maxMarginRatio: CGFloat = 0.35      // 최대 여백 비율 (35%)
    private let balanceThreshold: CGFloat = 0.08   // 균형 허용 오차 (8%)
    private let idealBottomRatio: CGFloat = 2.0     // 이상적인 하단:상단 비율 (2:1)

    // MARK: - 메인 분석 함수
    func analyze(bbox: CGRect, imageSize: CGSize, isNormalized: Bool = true) -> MarginAnalysisResult {

        // bbox를 픽셀 좌표로 변환
        let pixelBBox: CGRect
        if isNormalized {
            pixelBBox = CGRect(
                x: bbox.origin.x * imageSize.width,
                y: bbox.origin.y * imageSize.height,
                width: bbox.width * imageSize.width,
                height: bbox.height * imageSize.height
            )
        } else {
            pixelBBox = bbox
        }

        // 절대 여백 계산
        let left = pixelBBox.origin.x
        let right = imageSize.width - (pixelBBox.origin.x + pixelBBox.width)
        let top = pixelBBox.origin.y
        let bottom = imageSize.height - (pixelBBox.origin.y + pixelBBox.height)

        // 비율 계산
        let leftRatio = left / imageSize.width
        let rightRatio = right / imageSize.width
        let topRatio = top / imageSize.height
        let bottomRatio = bottom / imageSize.height

        // 균형 점수 계산
        let horizontalBalance = calculateHorizontalBalance(leftRatio: leftRatio, rightRatio: rightRatio)
        let verticalBalance = calculateVerticalBalance(topRatio: topRatio, bottomRatio: bottomRatio)
        let overallBalance = (horizontalBalance + verticalBalance) / 2.0

        // 피드백 생성
        let (horizontalFeedback, horizontalDirection) = generateHorizontalFeedback(leftRatio: leftRatio, rightRatio: rightRatio)
        let (verticalFeedback, verticalDirection) = generateVerticalFeedback(topRatio: topRatio, bottomRatio: bottomRatio)

        // 이동 방향 계산
        let movementAmount = max(abs(leftRatio - rightRatio), abs(topRatio - bottomRatio))
        let movement: MovementDirection? = (horizontalDirection != nil || verticalDirection != nil) ?
            MovementDirection(horizontal: horizontalDirection, vertical: verticalDirection, amount: movementAmount) : nil

        return MarginAnalysisResult(
            left: left,
            right: right,
            top: top,
            bottom: bottom,
            leftRatio: leftRatio,
            rightRatio: rightRatio,
            topRatio: topRatio,
            bottomRatio: bottomRatio,
            horizontalBalance: horizontalBalance,
            verticalBalance: verticalBalance,
            overallBalance: overallBalance,
            horizontalFeedback: horizontalFeedback,
            verticalFeedback: verticalFeedback,
            movementDirection: movement
        )
    }

    // MARK: - 레퍼런스와 비교 분석
    func compareWithReference(
        current: CGRect,
        reference: CGRect,
        currentImageSize: CGSize,
        referenceImageSize: CGSize
    ) -> MarginComparisonResult {

        let currentMargins = analyze(bbox: current, imageSize: currentImageSize)
        let referenceMargins = analyze(bbox: reference, imageSize: referenceImageSize)

        // 비율 차이 계산
        let leftDiff = currentMargins.leftRatio - referenceMargins.leftRatio
        let rightDiff = currentMargins.rightRatio - referenceMargins.rightRatio
        let topDiff = currentMargins.topRatio - referenceMargins.topRatio
        let bottomDiff = currentMargins.bottomRatio - referenceMargins.bottomRatio

        // 매칭 점수 (0.0 ~ 1.0)
        let horizontalMatch = 1.0 - min(abs(leftDiff) + abs(rightDiff), 1.0)
        let verticalMatch = 1.0 - min(abs(topDiff) + abs(bottomDiff), 1.0)
        let overallMatch = (horizontalMatch + verticalMatch) / 2.0

        // 구체적인 조정 피드백
        let adjustmentFeedback = generateAdjustmentFeedback(
            leftDiff: leftDiff,
            rightDiff: rightDiff,
            topDiff: topDiff,
            bottomDiff: bottomDiff
        )

        return MarginComparisonResult(
            currentMargins: currentMargins,
            referenceMargins: referenceMargins,
            horizontalMatch: horizontalMatch,
            verticalMatch: verticalMatch,
            overallMatch: overallMatch,
            adjustmentFeedback: adjustmentFeedback
        )
    }

    // MARK: - Private Methods

    private func calculateHorizontalBalance(leftRatio: CGFloat, rightRatio: CGFloat) -> CGFloat {
        // 좌우 균형: 차이가 작을수록 1.0에 가까움
        let diff = abs(leftRatio - rightRatio)
        return max(0, 1.0 - (diff / 0.5))  // 50% 차이면 0점
    }

    private func calculateVerticalBalance(topRatio: CGFloat, bottomRatio: CGFloat) -> CGFloat {
        // 상하 균형: 하단이 상단의 약 2배가 이상적
        // 예: top=0.1, bottom=0.2 → 이상적
        let idealBottom = topRatio * idealBottomRatio
        let diff = abs(bottomRatio - idealBottom)
        return max(0, 1.0 - (diff / 0.3))  // 30% 차이면 0점
    }

    private func generateHorizontalFeedback(leftRatio: CGFloat, rightRatio: CGFloat) -> (String?, MovementDirection.HorizontalDirection?) {
        let diff = leftRatio - rightRatio

        if abs(diff) < balanceThreshold {
            return (nil, nil)  // 균형 잡힘
        }

        if diff > 0 {
            // 왼쪽 여백이 더 큼 → 카메라를 오른쪽으로
            let percentage = Int(abs(diff) * 100)
            return ("카메라를 오른쪽으로 \(percentage)% 이동", .right)
        } else {
            // 오른쪽 여백이 더 큼 → 카메라를 왼쪽으로
            let percentage = Int(abs(diff) * 100)
            return ("카메라를 왼쪽으로 \(percentage)% 이동", .left)
        }
    }

    private func generateVerticalFeedback(topRatio: CGFloat, bottomRatio: CGFloat) -> (String?, MovementDirection.VerticalDirection?) {
        // 이상적 비율: 하단이 상단의 2배
        let idealBottom = topRatio * idealBottomRatio
        let diff = bottomRatio - idealBottom

        if abs(diff) < balanceThreshold {
            return (nil, nil)  // 균형 잡힘
        }

        // 여백 부족 체크
        if topRatio < minMarginRatio {
            return ("상단 여백이 부족합니다", .down)
        }
        if bottomRatio < minMarginRatio {
            return ("하단 여백이 부족합니다", .up)
        }

        // 균형 조정
        if diff > 0 {
            // 하단 여백이 너무 큼 → 카메라를 아래로
            return ("카메라를 아래로 이동", .down)
        } else {
            // 하단 여백이 부족 → 카메라를 위로
            return ("카메라를 위로 이동", .up)
        }
    }

    private func generateAdjustmentFeedback(
        leftDiff: CGFloat,
        rightDiff: CGFloat,
        topDiff: CGFloat,
        bottomDiff: CGFloat
    ) -> String {
        var feedbacks: [String] = []
        let threshold: CGFloat = 0.05  // 5% 이상 차이나면 피드백

        // 수평 조정
        let horizontalShift = (leftDiff - rightDiff) / 2
        if abs(horizontalShift) > threshold {
            if horizontalShift > 0 {
                feedbacks.append("← 왼쪽으로")
            } else {
                feedbacks.append("→ 오른쪽으로")
            }
        }

        // 수직 조정
        let verticalShift = (topDiff - bottomDiff) / 2
        if abs(verticalShift) > threshold {
            if verticalShift > 0 {
                feedbacks.append("↑ 위로")
            } else {
                feedbacks.append("↓ 아래로")
            }
        }

        if feedbacks.isEmpty {
            return "✓ 레퍼런스와 일치"
        }

        return feedbacks.joined(separator: " | ")
    }
}

// MARK: - 비교 결과
struct MarginComparisonResult {
    let currentMargins: MarginAnalysisResult
    let referenceMargins: MarginAnalysisResult
    let horizontalMatch: CGFloat  // 0.0 ~ 1.0
    let verticalMatch: CGFloat    // 0.0 ~ 1.0
    let overallMatch: CGFloat     // 0.0 ~ 1.0
    let adjustmentFeedback: String

    var isMatched: Bool {
        return overallMatch > 0.85
    }
}
