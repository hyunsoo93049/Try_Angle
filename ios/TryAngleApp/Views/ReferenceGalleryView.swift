import SwiftUI

struct ReferenceGalleryView: View {
    @State private var selectedCategory = "Hot"
    @State private var searchText = ""
    @Environment(\.presentationMode) var presentationMode

    let categories = ["My", "Hot", "Cafe☕️", "Winter ☃️", "Street 🚶‍♂️", "랜드마크🗽"]

    // 샘플 이미지 (SF Symbols 사용)
    let sampleImages = Array(1...20)

    var body: some View {
        GeometryReader { geometry in
            let safeAreaTop = geometry.safeAreaInsets.top

            ZStack {
                Color.white.ignoresSafeArea()

                VStack(spacing: 0) {
                    // 상단 바 + 검색
                    VStack(spacing: 8) {
                        // 뒤로가기 버튼
                        HStack {
                            Button(action: {
                                // 카메라 탭으로 이동하려면 부모 뷰에서 처리 필요
                            }) {
                                Image(systemName: "chevron.left")
                                    .font(.system(size: 18, weight: .medium))
                                    .foregroundColor(.black)
                                    .frame(width: 29, height: 29)
                                    .background(Color(hex: "#ececec"))
                                    .clipShape(Circle())
                            }
                            .padding(.leading, 10)

                            Spacer()
                        }
                        .padding(.top, max(safeAreaTop, 10) + 15)

                    // 검색바
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass")
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "#454545"))

                        Text("스타일 검색")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(Color(hex: "#454545"))

                        Spacer()
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color(hex: "#ececec"))
                    .cornerRadius(99)
                    .padding(.horizontal, 10)

                    // 카테고리 탭
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 3) {
                            ForEach(categories, id: \.self) { category in
                                CategoryTab(
                                    title: category,
                                    isSelected: selectedCategory == category,
                                    action: { selectedCategory = category }
                                )
                            }
                        }
                        .padding(.horizontal, 10)
                    }
                    .frame(height: 37)
                }
                .background(Color.white)

                // 그리드 콘텐츠
                ScrollView {
                    LazyVGrid(columns: [
                        GridItem(.flexible(), spacing: 5),
                        GridItem(.flexible(), spacing: 5)
                    ], spacing: 15) {
                        ForEach(sampleImages, id: \.self) { index in
                            PhotoCard(imageName: "photo.\(index % 3 + 1)")
                        }
                    }
                    .padding(.horizontal, 10)
                    .padding(.top, 10)
                    .padding(.bottom, 220) // 하단 탭바 공간 확보
                }
            }
        }
        }
    }
}

// MARK: - 카테고리 탭
struct CategoryTab: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 0) {
                Text(title)
                    .font(.system(size: 15, weight: isSelected ? .bold : .medium))
                    .foregroundColor(Color(hex: "#555555"))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 10)

                // 밑줄
                Rectangle()
                    .fill(isSelected ? Color(hex: "#555555") : Color.clear)
                    .frame(height: 4)
            }
        }
    }
}

// MARK: - 포토카드
struct PhotoCard: View {
    let imageName: String
    @State private var isFavorite = false

    var body: some View {
        VStack(alignment: .trailing, spacing: 15) {
            // 이미지 (placeholder)
            RoundedRectangle(cornerRadius: 8)
                .fill(
                    LinearGradient(
                        colors: [Color(hex: "#e0e0e0"), Color(hex: "#f5f5f5")],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 184, height: 184)
                .overlay(
                    Image(systemName: "photo")
                        .font(.system(size: 40))
                        .foregroundColor(.gray.opacity(0.5))
                )

            // 하트 버튼
            Button(action: { isFavorite.toggle() }) {
                Image(systemName: isFavorite ? "heart.fill" : "heart")
                    .font(.system(size: 18))
                    .foregroundColor(isFavorite ? .red : .black)
            }
            .padding(.trailing, 8)
        }
    }
}

struct ReferenceGalleryView_Previews: PreviewProvider {
    static var previews: some View {
        ReferenceGalleryView()
    }
}
