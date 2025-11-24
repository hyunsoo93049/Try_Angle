import SwiftUI
import Photos

struct GalleryView: View {
    @State private var photos: [PHAsset] = []
    @State private var selectedPhoto: PHAsset?

    var body: some View {
        GeometryReader { geometry in
            let safeAreaTop = geometry.safeAreaInsets.top

            ZStack {
                Color.black.ignoresSafeArea()

                VStack(spacing: 0) {
                    // 상단 바
                    HStack {
                        Text("갤러리")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(.white)

                        Spacer()
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, max(safeAreaTop, 10) + 10)
                    .padding(.bottom, 10)

                // 사진 그리드
                ScrollView {
                    LazyVGrid(columns: [
                        GridItem(.flexible(), spacing: 1),
                        GridItem(.flexible(), spacing: 1),
                        GridItem(.flexible(), spacing: 1)
                    ], spacing: 1) {
                        ForEach(photos, id: \.localIdentifier) { asset in
                            GalleryPhotoItem(asset: asset)
                                .aspectRatio(1, contentMode: .fill)
                                .onTapGesture {
                                    selectedPhoto = asset
                                }
                        }
                    }
                    .padding(.bottom, 220) // 하단 탭바 공간 확보
                }
            }
        }
        }
        .onAppear {
            loadPhotos()
        }
    }

    // 사진 앨범에서 사진 불러오기
    private func loadPhotos() {
        let fetchOptions = PHFetchOptions()
        fetchOptions.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]

        let fetchResult = PHAsset.fetchAssets(with: .image, options: fetchOptions)
        var loadedPhotos: [PHAsset] = []

        fetchResult.enumerateObjects { asset, _, _ in
            loadedPhotos.append(asset)
        }

        photos = loadedPhotos
    }
}

// MARK: - 갤러리 사진 아이템
struct GalleryPhotoItem: View {
    let asset: PHAsset
    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image = image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else {
                Rectangle()
                    .fill(Color.gray.opacity(0.3))
            }
        }
        .onAppear {
            loadImage()
        }
    }

    private func loadImage() {
        let manager = PHImageManager.default()
        let options = PHImageRequestOptions()
        options.deliveryMode = .opportunistic
        options.isSynchronous = false

        manager.requestImage(
            for: asset,
            targetSize: CGSize(width: 200, height: 200),
            contentMode: .aspectFill,
            options: options
        ) { img, _ in
            if let img = img {
                DispatchQueue.main.async {
                    self.image = img
                }
            }
        }
    }
}

struct GalleryView_Previews: PreviewProvider {
    static var previews: some View {
        GalleryView()
    }
}
