import Foundation
import CoreGraphics

// MARK: - Pose Keypoint

/// 포즈 키포인트 (위치 + 신뢰도)
struct PoseKeypoint {
    let location: CGPoint
    let confidence: Float
}

// MARK: - Camera Aspect Ratio

/// 카메라 비율
enum CameraAspectRatio: String, Codable, CaseIterable, Hashable {
    case ratio16_9 = "16:9"
    case ratio4_3 = "4:3"
    case ratio1_1 = "1:1"

    var displayName: String { rawValue }

    var ratio: CGFloat {
        switch self {
        case .ratio16_9: return 16.0 / 9.0
        case .ratio4_3: return 4.0 / 3.0
        case .ratio1_1: return 1.0
        }
    }

    /// 레퍼런스 이미지로부터 비율 감지
    static func detect(from size: CGSize) -> CameraAspectRatio {
        // 세로/가로 무관하게 긴 변 / 짧은 변으로 비율 계산
        let longSide = max(size.width, size.height)
        let shortSide = min(size.width, size.height)
        let ratio = longSide / shortSide

        // 가장 가까운 비율 찾기
        let ratios: [(CameraAspectRatio, CGFloat)] = [
            (.ratio16_9, abs(ratio - 16.0/9.0)),
            (.ratio4_3, abs(ratio - 4.0/3.0)),
            (.ratio1_1, abs(ratio - 1.0))
        ]

        return ratios.min(by: { $0.1 < $1.1 })?.0 ?? .ratio4_3
    }
}

// MARK: - Feedback Category System

/// 피드백 카테고리 (우선순위 순서)
enum FeedbackCategory: String, Codable, CaseIterable {
    case pose = "pose"               // 1순위: 포즈
    case position = "position"       // 2순위: 인물 위치 (프레임 내)
    case framing = "framing"         // 3순위: 프레이밍 (거리/줌)
    case angle = "angle"             // 4순위: 카메라 앵글
    case composition = "composition" // 5순위: 구도
    case gaze = "gaze"               // 6순위: 시선

    /// 카테고리별 우선순위 (낮을수록 높은 우선순위)
    var priority: Int {
        switch self {
        case .pose: return 1
        case .position: return 2
        case .framing: return 3
        case .angle: return 4
        case .composition: return 5
        case .gaze: return 6
        }
    }

    /// 카테고리 한글 이름
    var displayName: String {
        switch self {
        case .pose: return "포즈"
        case .position: return "인물 위치"
        case .framing: return "프레이밍"
        case .angle: return "카메라 앵글"
        case .composition: return "구도"
        case .gaze: return "시선"
        }
    }

    /// 카테고리별 아이콘
    var icon: String {
        switch self {
        case .pose: return "💪"
        case .position: return "📍"
        case .framing: return "🔍"
        case .angle: return "📷"
        case .composition: return "🎨"
        case .gaze: return "👀"
        }
    }

    /// 기존 category 문자열을 FeedbackCategory로 매핑
    static func from(categoryString: String) -> FeedbackCategory? {
        // 포즈 관련
        if categoryString.hasPrefix("pose_") || categoryString == "pose" {
            return .pose
        }

        // 위치 관련
        if categoryString == "position_x" || categoryString == "position_y" {
            return .position
        }

        // 프레이밍 관련 (거리/줌/비율/여백/사진학 프레이밍)
        if categoryString == "distance" || categoryString == "aspect_ratio" || categoryString == "padding" || categoryString == "framing" || categoryString == "photography_framing" {
            return .framing
        }

        // 앵글 관련
        if categoryString == "camera_angle" || categoryString == "tilt" {
            return .angle
        }

        // 구도 관련
        if categoryString == "composition" {
            return .composition
        }

        // 시선 관련
        if categoryString == "gaze" || categoryString == "face_yaw" {
            return .gaze
        }

        return nil
    }
}

/// 카테고리별 상태 (UI 체크 표시용)
struct CategoryStatus: Identifiable, Equatable {
    let category: FeedbackCategory
    let isSatisfied: Bool           // 만족 여부 (체크 표시)
    let activeFeedbacks: [FeedbackItem]  // 현재 활성화된 피드백들

    var id: String { category.rawValue }

    /// 카테고리별 우선순위
    var priority: Int { category.priority }

    /// 대표 피드백 메시지 (가장 우선순위 높은 것)
    var primaryMessage: String? {
        activeFeedbacks.first?.message
    }
}

// MARK: - API Response Models

struct AnalysisResponse: Codable {
    let userFeedback: [FeedbackItem]
    let cameraSettings: CameraSettings
    let processingTime: String
    let timestamp: Double
}

struct FeedbackItem: Codable, Identifiable, Equatable {
    let priority: Int
    let icon: String
    let message: String
    let category: String

    // 실시간 진행도 추적
    let currentValue: Double?      // 현재 값 (예: 현재 기울기 10도)
    let targetValue: Double?       // 목표 값 (예: 목표 기울기 0도)
    let tolerance: Double?         // 허용 오차 (예: ±3도)
    let unit: String?              // 단위 (예: "도", "걸음")

    // 🔥 ID를 category만으로 하면 같은 카테고리는 숫자만 업데이트됨
    var id: String { category }

    // 진행률 계산 (0.0 ~ 1.0)
    var progress: Double {
        guard let current = currentValue,
              let target = targetValue else {
            return 0.0
        }

        let diff = abs(target - current)
        let maxDiff = abs(target) + 50.0 // 최대 차이를 임의로 설정
        return max(0.0, min(1.0, 1.0 - (diff / maxDiff)))
    }

    // 완료 여부
    var isCompleted: Bool {
        guard let current = currentValue,
              let target = targetValue,
              let tol = tolerance else {
            return false
        }

        return abs(current - target) <= tol
    }

    // 초과 여부
    var isOvershot: Bool {
        guard let current = currentValue,
              let target = targetValue else {
            return false
        }

        // 목표를 넘어섰는지 체크
        return (target >= 0 && current > target) || (target < 0 && current < target)
    }
}

struct CameraSettings: Codable {
    let iso: Int?
    let wbKelvin: Int?
    let evCompensation: Double?

    enum CodingKeys: String, CodingKey {
        case iso
        case wbKelvin
        case evCompensation
    }
}

// MARK: - Completed Feedback Tracking

/// 완료된 피드백 (사라지는 애니메이션용)
struct CompletedFeedback: Identifiable, Equatable {
    let item: FeedbackItem
    let completedAt: Date

    var id: String { item.id }

    /// 완료된 지 얼마나 지났는지 (초)
    var elapsedTime: TimeInterval {
        Date().timeIntervalSince(completedAt)
    }

    /// 아직 표시되어야 하는지 (2초 동안 표시)
    var shouldDisplay: Bool {
        elapsedTime < 2.0
    }

    /// 페이드아웃 진행도 (0.0 ~ 1.0, 1.5초부터 페이드 시작)
    var fadeProgress: Double {
        if elapsedTime < 1.5 {
            return 1.0  // 완전히 보임
        } else {
            // 1.5초 ~ 2.0초 사이에 페이드아웃
            let fadeTime = elapsedTime - 1.5
            return max(0.0, 1.0 - (fadeTime / 0.5))
        }
    }
}
