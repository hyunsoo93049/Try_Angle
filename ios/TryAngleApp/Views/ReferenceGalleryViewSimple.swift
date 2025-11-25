import SwiftUI

struct ReferenceGalleryViewSimple: View {
    @Binding var selectedTab: Int
    let onSelectImage: (UIImage) -> Void  // 이미지 선택 콜백

    @State private var selectedCategoryIndex = 1  // Hot부터 시작
    @State private var searchText = ""
    @AppStorage("mySavedPhotos") private var savedPhotosData: String = ""

    private var mySavedPhotos: [String] {
        savedPhotosData.isEmpty ? [] : savedPhotosData.components(separatedBy: ",")
    }

    private func saveFavorite(_ imageName: String) {
        var photos = mySavedPhotos
        if photos.contains(imageName) {
            // 이미 있으면 제거
            photos.removeAll { $0 == imageName }
        } else {
            // 없으면 추가
            photos.append(imageName)
        }
        savedPhotosData = photos.joined(separator: ",")
    }

    private func isFavorite(_ imageName: String) -> Bool {
        return mySavedPhotos.contains(imageName)
    }

    let categories = ["My", "Hot", "Cafe☕️", "Winter ☃️", "Street 🚶‍♂️", "랜드마크🗽"]

    // 하드코딩된 이미지 목록 - 실제로 존재하는 파일들
    let imagesByCategory: [String: [String]] = [
        "Hot": ["hot1", "hot2", "hot3", "hot4", "hot5", "hot6", "hot7", "hot8"],
        "Cafe": ["IMG_9593", "IMG_9594", "IMG_9595", "IMG_9596", "IMG_9597", "IMG_9598", "IMG_9599", "IMG_9600"],
        "Winter": ["winter1", "winter2", "winter3", "winter4", "winter5", "winter6", "winter7", "winter8"],
        "Street": ["IMG_9616", "IMG_9617", "IMG_9618", "IMG_9619", "IMG_9620", "IMG_9621", "IMG_9622", "IMG_9623"],
        "Landmark": ["landmark1", "landmark2", "landmark3", "landmark4", "landmark5", "landmark6", "landmark7", "landmark8"]
    ]

    private func getImagesForCategory(_ index: Int) -> [String] {
        let categoryNames = ["My", "Hot", "Cafe", "Winter", "Street", "Landmark"]
        let folderName = categoryNames[index]

        if folderName == "My" {
            return mySavedPhotos
        }

        return imagesByCategory[folderName] ?? []
    }

    var body: some View {
        GeometryReader { geometry in
            let safeAreaTop = geometry.safeAreaInsets.top

            ZStack(alignment: .top) {
                Color.white.ignoresSafeArea()

                VStack(spacing: 0) {
                    // 상단 영역
                    Color.white
                        .frame(height: safeAreaTop + 40)

                    // 뒤로가기 버튼
                    HStack {
                        Button(action: {
                            selectedTab = 1  // 카메라 탭으로 이동
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

                    // 카테고리 탭
                    ScrollViewReader { scrollProxy in
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 3) {
                                ForEach(Array(categories.enumerated()), id: \.offset) { index, category in
                                    CategoryTab(
                                        title: category,
                                        isSelected: selectedCategoryIndex == index,
                                        action: {
                                            withAnimation {
                                                selectedCategoryIndex = index
                                            }
                                        }
                                    )
                                    .id(index)
                                }
                            }
                            .padding(.horizontal, 10)
                        }
                        .frame(height: 37)
                        .onChange(of: selectedCategoryIndex) { newIndex in
                            withAnimation {
                                scrollProxy.scrollTo(newIndex, anchor: .center)
                            }
                        }
                    }

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

                    // 이미지 그리드
                    TabView(selection: $selectedCategoryIndex) {
                        ForEach(Array(categories.enumerated()), id: \.offset) { index, category in
                            Group {
                                if index == 0 {
                                    // My 카테고리
                                    if mySavedPhotos.isEmpty {
                                        VStack {
                                            Spacer()
                                            Text("아직 저장한 사진이 없어요\n\n마음에 드는 사진을 골라주세요")
                                                .font(.system(size: 20, weight: .medium))
                                                .multilineTextAlignment(.center)
                                                .foregroundColor(.black)
                                            Spacer()
                                        }
                                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                                        .background(Color.white)
                                    } else {
                                        ScrollView {
                                            LazyVGrid(columns: [
                                                GridItem(.flexible(), spacing: 5),
                                                GridItem(.flexible(), spacing: 5)
                                            ], spacing: 15) {
                                                ForEach(mySavedPhotos, id: \.self) { photoName in
                                                    SimplePhotoCard(
                                                        imageName: photoName,
                                                        isFavorite: isFavorite(photoName),
                                                        onToggleFavorite: { saveFavorite(photoName) },
                                                        onSelectImage: onSelectImage
                                                    )
                                                }
                                            }
                                            .padding(.horizontal, 10)
                                            .padding(.top, 10)
                                            .padding(.bottom, 90)
                                        }
                                    }
                                } else {
                                    // 다른 카테고리
                                    let images = getImagesForCategory(index)
                                    ScrollView {
                                        LazyVGrid(columns: [
                                            GridItem(.flexible(), spacing: 5),
                                            GridItem(.flexible(), spacing: 5)
                                        ], spacing: 15) {
                                            ForEach(images, id: \.self) { imageName in
                                                SimplePhotoCard(
                                                    imageName: imageName,
                                                    isFavorite: isFavorite(imageName),
                                                    onToggleFavorite: { saveFavorite(imageName) },
                                                    onSelectImage: onSelectImage
                                                )
                                            }
                                        }
                                        .padding(.horizontal, 10)
                                        .padding(.top, 10)
                                        .padding(.bottom, 90)
                                    }
                                }
                            }
                            .tag(index)
                        }
                    }
                    .tabViewStyle(.page(indexDisplayMode: .never))
                    .padding(.top, 5)
                }
            }
        }
    }
}

// 간단한 포토카드
struct SimplePhotoCard: View {
    let imageName: String
    let isFavorite: Bool
    let onToggleFavorite: () -> Void
    let onSelectImage: (UIImage) -> Void

    @State private var loadedImage: UIImage?
    @State private var showImageDetail = false

    var body: some View {
        VStack(alignment: .trailing, spacing: 15) {
            if let image = loadedImage {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 184, height: 184)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .onTapGesture {
                        showImageDetail = true
                    }
            } else {
                // 플레이스홀더
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
                        ProgressView()
                            .scaleEffect(0.8)
                    )
            }

            // 하트 버튼
            Button(action: onToggleFavorite) {
                Image(systemName: isFavorite ? "heart.fill" : "heart")
                    .font(.system(size: 18))
                    .foregroundColor(isFavorite ? .red : .black)
            }
            .padding(.trailing, 8)
        }
        .onAppear {
            loadImageFromBundle()
        }
        .fullScreenCover(isPresented: $showImageDetail) {
            if let image = loadedImage {
                ImageDetailView(
                    image: image,
                    onSelectImage: {
                        print("🟡 [SimplePhotoCard] onSelectImage 호출 (imageName: \(imageName))")
                        onSelectImage(image)
                        print("🟡 [SimplePhotoCard] 상위 onSelectImage 호출 완료")
                    }
                )
            }
        }
    }

    private func loadImageFromBundle() {
        // 다양한 방법으로 이미지 로드 시도

        // 1. UIImage(named:) 시도
        if let image = UIImage(named: imageName) {
            loadedImage = image
            return
        }

        // 2. 확장자 추가해서 시도
        for ext in [".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG"] {
            if let image = UIImage(named: imageName + ext) {
                loadedImage = image
                return
            }
        }

        // 3. Bundle.main.path 시도
        for ext in ["jpg", "JPG", "jpeg", "JPEG", "png", "PNG"] {
            if let path = Bundle.main.path(forResource: imageName, ofType: ext),
               let image = UIImage(contentsOfFile: path) {
                loadedImage = image
                return
            }
        }

        // 4. 전체 이름으로 시도 (IMG_9593.JPG 형식)
        let variations = [
            imageName,
            imageName.replacingOccurrences(of: "IMG", with: "IMG_"),
            "IMG_\(imageName.replacingOccurrences(of: "IMG", with: ""))"
        ]

        for name in variations {
            for ext in ["", ".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG"] {
                if let image = UIImage(named: name + ext) {
                    loadedImage = image
                    return
                }
            }
        }

        print("❌ 이미지 로드 실패: \(imageName)")
    }
}

