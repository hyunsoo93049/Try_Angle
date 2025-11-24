import SwiftUI

struct MainTabView: View {
    @State private var selectedTab = 1  // 0: 갤러리, 1: 카메라, 2: 레퍼런스

    var body: some View {
        ZStack(alignment: .bottom) {
            // 탭별 콘텐츠
            Group {
                if selectedTab == 0 {
                    GalleryView()
                } else if selectedTab == 1 {
                    ContentView()
                } else {
                    ReferenceGalleryView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // 커스텀 하단 탭바
            CustomTabBar(selectedTab: $selectedTab)
        }
        .ignoresSafeArea()
    }
}

// MARK: - 커스텀 탭바
struct CustomTabBar: View {
    @Binding var selectedTab: Int

    var body: some View {
        ZStack {
            // 배경
            Rectangle()
                .fill(Color.black.opacity(0.5))
                .frame(height: 211)
                .ignoresSafeArea(edges: .bottom)

            VStack(spacing: 0) {
                Spacer()

                // 셔터 버튼 (카메라 탭에서만 표시)
                if selectedTab == 1 {
                    HStack {
                        Spacer()

                        // 셔터 버튼
                        Circle()
                            .strokeBorder(Color.white, lineWidth: 4)
                            .frame(width: 82, height: 82)
                            .overlay(
                                Circle()
                                    .fill(Color.white)
                                    .frame(width: 68, height: 68)
                            )
                            .padding(.bottom, 20)

                        Spacer()

                        // 카메라 전환 버튼
                        Button(action: {}) {
                            Image(systemName: "arrow.triangle.2.circlepath.camera")
                                .font(.system(size: 24))
                                .foregroundColor(.white)
                                .frame(width: 41, height: 41)
                                .background(Color.gray.opacity(0.5))
                                .clipShape(Circle())
                        }
                        .padding(.trailing, 51)
                        .padding(.bottom, 40)
                    }
                }

                // 탭 레이블
                HStack(spacing: 77) {
                    TabButton(title: "갤러리", isSelected: selectedTab == 0) {
                        selectedTab = 0
                    }

                    TabButton(title: "카메라", isSelected: selectedTab == 1) {
                        selectedTab = 1
                    }

                    TabButton(title: "레퍼런스", isSelected: selectedTab == 2) {
                        selectedTab = 2
                    }
                }
                .padding(.bottom, 27)
            }
        }
        .frame(height: 211)
    }
}

// MARK: - 탭 버튼
struct TabButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(isSelected ? .white : Color(hex: "#5c5c5c"))
        }
    }
}

// MARK: - Hex Color Extension
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }

        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
