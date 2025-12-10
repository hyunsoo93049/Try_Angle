import SwiftUI

struct FeedbackOverlay: View {
    let feedbackItems: [FeedbackItem]
    let categoryStatuses: [CategoryStatus]  // 🗑️ 레거시 (호환용)
    let completedFeedbacks: [CompletedFeedback]
    let processingTime: String
    let gateEvaluation: GateEvaluation?  // 🆕 Gate System 평가 결과
    let unifiedFeedback: UnifiedFeedback?  // 🆕 통합 피드백 (하나의 동작 → 여러 Gate 해결)
    let stabilityProgress: Float  // 🆕 0.0 ~ 1.0 (Temporal Lock 진행도)

    let environmentWarning: String?  // 🆕 환경 경고 (너무 어두움 등)
    let currentShotDebugInfo: String? // 🆕 화면 표시용 샷타입 정보 (Debug Mode)

    var body: some View {
        let _ = {
            if !feedbackItems.isEmpty {
                print("🖥️ FeedbackOverlay: \(feedbackItems.count)개 피드백 받음")
            }
        }()

        ZStack {
            // 🆕 왼쪽 상단: Gate Progress (5단계 표시)
            VStack {
                HStack {
                    GateProgressView(evaluation: gateEvaluation)
                        .frame(width: 150)
                        .padding(.leading, 12)
                        .padding(.top, 120)
                    Spacer()
                }
                Spacer()
            }

            // 🆕 중앙: Temporal Lock (Circular Ring)
            if stabilityProgress > 0.0 {
                VStack {
                    Spacer()
                    ZStack {
                        CircularGateProgressView(progress: stabilityProgress)
                        
                        if stabilityProgress >= 1.0 {
                            Image(systemName: "camera.fill")
                                .font(.system(size: 30))
                                .foregroundColor(.white)
                                .transition(.scale.combined(with: .opacity))
                        }
                    }
                    .padding(.bottom, 300) // 피드백 텍스트 위쪽
                    Spacer()
                }
                .transition(.opacity)
                .animation(.easeInOut, value: stabilityProgress > 0)
            }

            // 기존 레이아웃: 상단 + 하단 피드백
            VStack(alignment: .leading, spacing: 12) {
                // 상단: 처리 시간
                HStack {
                    Spacer()
                    Text("⚡ \(processingTime)")
                        .font(.caption)
                        .foregroundColor(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.black.opacity(0.6))
                        .background(Color.black.opacity(0.6))
                        .cornerRadius(8)
                }
                .padding(.top, 60)
                .padding(.trailing, 16)
                
                // 🆕 상단 중앙: 샷타입 비교 가이드 (Debug Info)
                // 디버그 로그를 정제하여 UI로 표시
                if let debugInfo = currentShotDebugInfo {
                    HStack {
                        Spacer()
                        Text(debugInfo)
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.yellow) // 눈에 띄게 표시
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .background(Color.black.opacity(0.7)) // 가독성 확보
                            .cornerRadius(12)
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.yellow.opacity(0.5), lineWidth: 1))
                        Spacer()
                    }
                    .padding(.top, 108) // 처리 시간 아래쪽
                    .transition(.move(edge: .top).combined(with: .opacity))
                }

                Spacer()

                // 🆕 하단: 통합 피드백 표시 (하나의 동작 → 여러 Gate 해결)
                VStack(alignment: .leading, spacing: 8) {
                    // 완료된 피드백 (페이드아웃)
                    ForEach(completedFeedbacks) { completed in
                        CompletedFeedbackView(completed: completed)
                            .transition(.asymmetric(
                                insertion: .scale.combined(with: .opacity),
                                removal: .opacity
                            ))
                            .id(completed.id)
                    }

                    // 🆕 통합 피드백 뷰 (하나의 동작으로 여러 Gate 해결)
                    if let unified = unifiedFeedback {
                        // 🔒 Gate 0 (비율)은 별도 표시 - 동작이 아닌 설정 변경
                        if unified.affectedGates == [0] {
                            AspectRatioFeedbackView(
                                feedback: gateEvaluation?.gate0.feedback ?? "비율을 맞춰주세요"
                            )
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                            .id("aspect_ratio")
                        } else {
                            UnifiedFeedbackView(feedback: unified)
                                .transition(.move(edge: .bottom).combined(with: .opacity))
                                .id(unified.stableId)
                        }
                    } else if let currentFeedback = currentGateFeedback {
                        // 폴백: 기존 Gate 피드백 뷰
                        GateFeedbackView(
                            feedback: currentFeedback,
                            gateIndex: gateEvaluation?.currentFailedGate ?? 0
                        )
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                        .id(currentFeedback)
                    }
                }
                .animation(.spring(response: 0.4, dampingFraction: 0.8), value: completedFeedbacks.map { $0.id })
                .animation(.spring(response: 0.5, dampingFraction: 0.85), value: unifiedFeedback?.stableId ?? currentGateFeedback)  // 🔑 안정적인 애니메이션
                .padding(.horizontal, 16)
                .padding(.bottom, 120)
            }
            
            // 🆕 환경 경고 (최상단)
            if let warning = environmentWarning {
                VStack {
                    Text(warning)
                        .font(.headline)
                        .foregroundColor(.white)
                        .padding()
                        .background(Color.red.opacity(0.8))
                        .cornerRadius(12)
                        .padding(.top, 100)
                    Spacer()
                }
                .transition(.move(edge: .top).combined(with: .opacity))
                .animation(.easeInOut, value: warning)
            }
        }
    }

    // 🆕 현재 Gate의 피드백 메시지
    private var currentGateFeedback: String? {
        guard let eval = gateEvaluation else { return nil }
        if eval.allPassed { return nil }
        return eval.primaryFeedback
    }

    // 카테고리별 강조 색상
    private func categoryColor(_ category: String) -> Color {
        switch category {
        case "pose":
            return .purple
        case "distance":
            return .blue
        case "composition":
            return .orange
        default:
            return .gray
        }
    }
}

// MARK: - 개별 피드백 아이템 뷰 (실시간 진행도 표시)
struct FeedbackItemView: View {
    let item: FeedbackItem

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // 상단: 아이콘 + 메시지
            HStack(spacing: 12) {
                Text(item.icon)
                    .font(.title2)

                Text(item.message)
                    .font(.body)
                    .foregroundColor(.white)
                    .lineLimit(2)

                Spacer()

                // 완료 체크 표시
                if item.isCompleted {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.green)
                }
            }

            // 하단: 실시간 진행도 표시
            if let current = item.currentValue,
               let target = item.targetValue,
               let unit = item.unit {

                HStack(spacing: 12) {
                    // 현재값 → 목표값
                    Text(String(format: "%.0f%@ → %.0f%@", current, unit, target, unit))
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.8))
                        .monospacedDigit()

                    Spacer()

                    // 차이값 표시
                    let diff = abs(target - current)
                    Text(String(format: "차이: %.0f%@", diff, unit))
                        .font(.caption)
                        .foregroundColor(diff <= (item.tolerance ?? 3.0) ? .green : .orange)
                        .monospacedDigit()
                }

                // 프로그레스 바
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        // 배경
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.white.opacity(0.2))
                            .frame(height: 8)

                        // 진행 바
                        RoundedRectangle(cornerRadius: 4)
                            .fill(progressColor)
                            .frame(width: geometry.size.width * progressWidth, height: 8)
                            .animation(.easeInOut(duration: 0.3), value: progressWidth)
                    }
                }
                .frame(height: 8)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            Color.black.opacity(0.7)
                .overlay(
                    categoryColor(item.category)
                        .frame(width: 4),
                    alignment: .leading
                )
        )
        .cornerRadius(12)
    }

    // 진행도 바 너비 계산
    private var progressWidth: CGFloat {
        guard let current = item.currentValue,
              let target = item.targetValue else {
            return 0.0
        }

        let diff = abs(target - current)
        let tolerance = item.tolerance ?? 3.0

        // 차이가 허용 오차 이내면 100%
        if diff <= tolerance {
            return 1.0
        }

        // 차이가 클수록 진행도 낮음 (최대 50도 기준)
        let maxDiff = 50.0
        return max(0.0, min(1.0, 1.0 - (diff / maxDiff)))
    }

    // 진행도에 따른 색상
    private var progressColor: Color {
        if item.isCompleted {
            return .green
        } else if progressWidth > 0.7 {
            return .yellow
        } else if progressWidth > 0.4 {
            return .orange
        } else {
            return .red
        }
    }

    // 카테고리별 강조 색상
    private func categoryColor(_ category: String) -> Color {
        switch category {
        case "pose":
            return .purple
        case "distance":
            return .blue
        case "composition":
            return .orange
        default:
            return .gray
        }
    }
}

// MARK: - 완료된 피드백 뷰 (초록색 + 페이드아웃)
struct CompletedFeedbackView: View {
    let completed: CompletedFeedback

    var body: some View {
        HStack(spacing: 12) {
            // 체크 아이콘
            Image(systemName: "checkmark.circle.fill")
                .font(.title2)
                .foregroundColor(.white)

            Text(completed.item.icon)
                .font(.title2)

            VStack(alignment: .leading, spacing: 4) {
                Text(completed.item.message)
                    .font(.body)
                    .foregroundColor(.white)
                    .lineLimit(2)

                Text("완료!")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
            }

            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            Color.green.opacity(0.9)
                .overlay(
                    Color.white.opacity(0.2)
                        .frame(width: 4),
                    alignment: .leading
                )
        )
        .cornerRadius(12)
        .shadow(color: .green.opacity(0.5), radius: 10, x: 0, y: 5)
        .opacity(completed.fadeProgress)
        .scaleEffect(completed.fadeProgress * 0.1 + 0.9)  // 살짝 작아지면서 사라짐
    }
}

// MARK: - 🆕 Gate 피드백 뷰 (현재 Gate의 피드백만 표시)
struct GateFeedbackView: View {
    let feedback: String
    let gateIndex: Int

    private let gateInfo: [(name: String, icon: String, color: Color)] = [
        ("비율", "📐", .blue),
        ("프레이밍", "📸", .orange),
        ("위치", "↔️", .purple),
        ("압축감", "🔭", .cyan),
        ("포즈", "🤸", .pink)
    ]

    var body: some View {
        let info = gateInfo[min(gateIndex, 4)]

        VStack(alignment: .leading, spacing: 8) {
            // 상단: Gate 정보
            HStack(spacing: 8) {
                // Gate 번호
                Text("Gate \(gateIndex + 1)")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.black)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.yellow)
                    .cornerRadius(4)

                Text(info.icon)
                    .font(.title2)

                Text(info.name)
                    .font(.system(size: 16, weight: .bold))
                    .foregroundColor(.white)

                Spacer()
            }

            // 피드백 메시지
            Text(feedback)
                .font(.body)
                .foregroundColor(.white)
                .lineLimit(2)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            Color.black.opacity(0.8)
                .overlay(
                    info.color.frame(width: 4),
                    alignment: .leading
                )
        )
        .cornerRadius(12)
    }
}

// MARK: - 🆕 통합 피드백 뷰 (하나의 동작 → 여러 Gate 해결)
struct UnifiedFeedbackView: View {
    let feedback: UnifiedFeedback

    private let gateInfo: [(name: String, icon: String, color: Color)] = [
        ("비율", "📐", .blue),
        ("프레이밍", "📸", .orange),
        ("위치", "↔️", .purple),
        ("압축감", "🔭", .cyan),
        ("포즈", "🤸", .pink)
    ]

    // 동작별 아이콘
    private func actionIcon(_ action: AdjustmentAction) -> String {
        switch action {
        case .moveForward: return "⬆️"
        case .moveBackward: return "⬇️"
        case .moveLeft: return "⬅️"
        case .moveRight: return "➡️"
        case .tiltUp: return "🔼"
        case .tiltDown: return "🔽"
        case .zoomIn: return "🔍"
        case .zoomOut: return "🔎"
        // 🆕 복합 동작
        case .zoomInThenMoveBack: return "🔍⬇️"
        case .zoomInThenMoveForward: return "🔍⬆️"
        case .zoomOutThenMoveBack: return "🔎⬇️"
        case .zoomOutThenMoveForward: return "🔎⬆️"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // 상단: 메인 동작 지시
            HStack(spacing: 12) {
                // 동작 아이콘
                Text(actionIcon(feedback.primaryAction))
                    .font(.system(size: 32))

                VStack(alignment: .leading, spacing: 2) {
                    // 메인 메시지 (크기 + 동작)
                    Text(feedback.mainMessage)
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(.white)

                    // 영향 받는 Gate 뱃지들
                    HStack(spacing: 6) {
                        ForEach(feedback.affectedGates, id: \.self) { gateIdx in
                            let info = gateInfo[min(gateIdx, 4)]
                            HStack(spacing: 2) {
                                Text(info.icon)
                                    .font(.system(size: 10))
                                Text(info.name)
                                    .font(.system(size: 10, weight: .medium))
                            }
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(info.color.opacity(0.3))
                            .cornerRadius(4)
                        }
                    }
                }

                Spacer()

                // 다중 Gate 해결 표시
                if feedback.affectedGates.count > 1 {
                    VStack(spacing: 2) {
                        Text("\(feedback.affectedGates.count)")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(.green)
                        Text("Gates")
                            .font(.system(size: 10))
                            .foregroundColor(.green.opacity(0.8))
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.green.opacity(0.2))
                    .cornerRadius(8)
                }
            }

            // 하단: 예상 결과들
            if !feedback.expectedResults.isEmpty {
                Divider()
                    .background(Color.white.opacity(0.3))

                VStack(alignment: .leading, spacing: 4) {
                    Text("예상 결과")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.white.opacity(0.6))

                    ForEach(feedback.expectedResults, id: \.self) { result in
                        HStack(spacing: 6) {
                            Image(systemName: "checkmark.circle")
                                .font(.system(size: 12))
                                .foregroundColor(.green.opacity(0.8))
                            Text(result)
                                .font(.system(size: 13))
                                .foregroundColor(.white.opacity(0.9))
                        }
                    }
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(
            LinearGradient(
                gradient: Gradient(colors: [
                    Color.black.opacity(0.85),
                    Color.black.opacity(0.75)
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .overlay(
                // 왼쪽 강조선 (첫 번째 영향 Gate 색상)
                gateInfo[min(feedback.priority, 4)].color.frame(width: 4),
                alignment: .leading
            )
        )
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.3), radius: 8, x: 0, y: 4)
    }
}

// MARK: - 🆕 비율 피드백 뷰 (Gate 0 - 설정 변경 유도)
struct AspectRatioFeedbackView: View {
    let feedback: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // 상단: 경고 아이콘 + 메시지
            HStack(spacing: 12) {
                // 비율 아이콘
                ZStack {
                    Circle()
                        .fill(Color.red.opacity(0.2))
                        .frame(width: 44, height: 44)

                    Text("📐")
                        .font(.system(size: 24))
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("비율 불일치")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(.red)

                    Text(feedback)
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(.white)
                }

                Spacer()
            }

            // 하단: 안내 메시지
            HStack(spacing: 6) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 12))
                    .foregroundColor(.yellow)

                Text("비율을 먼저 맞춰야 다음 단계로 진행됩니다")
                    .font(.system(size: 12))
                    .foregroundColor(.white.opacity(0.8))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(
            Color.black.opacity(0.85)
                .overlay(
                    Color.red.frame(width: 4),
                    alignment: .leading
                )
        )
        .cornerRadius(16)
        .shadow(color: .red.opacity(0.3), radius: 8, x: 0, y: 4)
    }
}

// MARK: - 카테고리 체크리스트 뷰 (레거시)
struct CategoryChecklistView: View {
    let categoryStatuses: [CategoryStatus]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(categoryStatuses) { status in
                CategoryCheckItem(status: status)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.black.opacity(0.6))
        )
    }
}

// MARK: - 개별 카테고리 체크 아이템
struct CategoryCheckItem: View {
    let status: CategoryStatus

    var body: some View {
        HStack(spacing: 6) {
            // 카테고리 이름
            Text(status.category.displayName)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(status.isSatisfied ? .white.opacity(0.7) : .white)

            // 체크 아이콘 (글자 바로 옆)
            Image(systemName: status.isSatisfied ? "checkmark.circle.fill" : "circle")
                .font(.system(size: 14))
                .foregroundColor(status.isSatisfied ? .green : .white.opacity(0.5))
                .animation(.easeInOut(duration: 0.3), value: status.isSatisfied)
        }
    }
}

struct FeedbackOverlay_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            // 통합 피드백 미리보기
            FeedbackOverlay(
                feedbackItems: [],
                categoryStatuses: [],
                completedFeedbacks: [],
                processingTime: "0.8s",
                gateEvaluation: nil,
                unifiedFeedback: UnifiedFeedback(
                    primaryAction: .moveForward,
                    magnitude: "한 걸음",
                    affectedGates: [1, 2, 3],
                    expectedResults: [
                        "샷 타입이 좁아집니다",
                        "좌우 균형이 맞춰집니다",
                        "배경 압축이 자연스러워집니다"
                    ],
                    priority: 1
                ),
                stabilityProgress: 0.5,
                environmentWarning: nil,
                currentShotDebugInfo: "현재: 전신샷 vs 목표: 허벅지샷"
            )

            // 기존 Gate 피드백 미리보기
            FeedbackOverlay(
                feedbackItems: [
                    FeedbackItem(
                        priority: 1,
                        icon: "💪",
                        message: "왼팔을 더 올려주세요",
                        category: "pose_left_arm",
                        currentValue: 45.0,
                        targetValue: 90.0,
                        tolerance: 10.0,
                        unit: "도"
                    )
                ],
                categoryStatuses: [
                    CategoryStatus(category: .pose, isSatisfied: false, activeFeedbacks: []),
                    CategoryStatus(category: .position, isSatisfied: true, activeFeedbacks: [])
                ],
                completedFeedbacks: [],
                processingTime: "0.8s",
                gateEvaluation: nil,
                unifiedFeedback: nil,
                stabilityProgress: 0.0,
                environmentWarning: "너무 어두워요 💡",
                currentShotDebugInfo: nil
            )
        }
        .background(Color.black)
    }
}


// MARK: - 🆕 Temporal Lock UI (Circular Ring)
struct CircularGateProgressView: View {
    let progress: Float
    
    var body: some View {
        ZStack {
            // 배경 링
            Circle()
                .stroke(Color.white.opacity(0.3), lineWidth: 6)
            
            // 진행 링 (반시계 방향 CCW)
            // SwiftUI trim은 기본적으로 시계방향이므로, scaleEffect(x:-1)로 반전
            Circle()
                .trim(from: 0.0, to: CGFloat(progress))
                .stroke(
                    progress >= 1.0 ? Color.green : Color.yellow,
                    style: StrokeStyle(lineWidth: 6, lineCap: .round)
                )
                .rotationEffect(Angle(degrees: -90)) // 12시 방향부터 시작
                .scaleEffect(x: -1, y: 1) // 반시계 방향으로 채우기
                .animation(.linear(duration: 0.05), value: progress)
        }
        .frame(width: 80, height: 80)
        .shadow(color: .black.opacity(0.3), radius: 4)
    }
}
