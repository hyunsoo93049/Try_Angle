import SwiftUI
import Photos

struct ContentView: View {
    // MARK: - State
    @StateObject private var cameraManager = CameraManager()
    @StateObject private var realtimeAnalyzer = RealtimeAnalyzer()  // 실시간 분석
    @State private var referenceImage: UIImage?
    @State private var feedbackItems: [FeedbackItem] = []
    @State private var serverFeedbackItems: [FeedbackItem] = []  // 서버 피드백 (포즈 등)
    @State private var processingTime: String = ""
    @State private var isAnalyzing = false
    @State private var errorMessage: String?
    @State private var analysisTimer: Timer?
    @State private var frameUpdateTimer: Timer?  // 실시간 프레임 분석용

    // 안드로이드 기능 추가
    @State private var showGrid = false
    @State private var showFPS = false
    @State private var zoomLevel: CGFloat = 1.0
    @State private var analysisEnabled = true  // 분석 모드 on/off
    @State private var autoCapture = true  // 자동 촬영 모드
    @State private var capturedImage: UIImage?  // 촬영된 이미지
    @State private var showCaptureFlash = false  // 촬영 플래시 효과

    // 🆕 비율 선택
    @State private var selectedAspectRatio: CameraAspectRatio = .ratio4_3
    @State private var showAspectRatioMenu = false
    @State private var debugAlert = false

    // 통합 피드백 (실시간 + 서버)
    private var combinedFeedback: [FeedbackItem] {
        var combined: [FeedbackItem] = []

        // 1순위: 실시간 피드백 (프레이밍, 구도)
        combined.append(contentsOf: realtimeAnalyzer.instantFeedback)

        // 2순위: 서버 피드백 (포즈) - 실시간 피드백과 중복되지 않는 것만
        let realtimeCategories = Set(realtimeAnalyzer.instantFeedback.map { $0.category })
        let uniqueServerFeedback = serverFeedbackItems.filter {
            !realtimeCategories.contains($0.category) && $0.category == "pose"
        }
        combined.append(contentsOf: uniqueServerFeedback)

        // 우선순위로 정렬하고 상위 5개만 반환
        return Array(combined.sorted { $0.priority < $1.priority }.prefix(5))
    }

    // 피드백 업데이트
    private func updateCombinedFeedback() {
        // combinedFeedback은 computed property라서 자동 업데이트됨
        // 필요시 추가 로직
    }

    // 사진 촬영
    private func performCapture() {
        guard let currentFrame = cameraManager.currentFrame else { return }

        // 플래시 효과
        withAnimation(.easeInOut(duration: 0.2)) {
            showCaptureFlash = true
        }

        let fixedImage: UIImage

        // 픽셀 비율 확인하여 landscape/portrait 처리
        guard let cgImage = currentFrame.cgImage else { return }
        let actualWidth = cgImage.width
        let actualHeight = cgImage.height

        if actualWidth > actualHeight {
            // 픽셀이 가로 방향 (landscape)이면 회전하지 않고 orientation만 .up으로 설정
            // 이렇게 해야 사진 앱에서 가로 사진으로 올바르게 표시됨
            fixedImage = UIImage(cgImage: cgImage, scale: currentFrame.scale, orientation: .up)
        } else {
            // 픽셀이 세로 방향 (portrait)이면 fixedOrientation() 적용
            fixedImage = currentFrame.fixedOrientation()
        }

        // 회전된 이미지를 크롭
        let croppedImage = cropImage(fixedImage, to: selectedAspectRatio)

        // 이미지 저장
        capturedImage = croppedImage

        // 🔧 사진 앨범에 저장
        saveImageToPhotoLibrary(croppedImage)

        // 플래시 효과 제거
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            withAnimation(.easeInOut(duration: 0.2)) {
                showCaptureFlash = false
            }

            // 성공 알림
            print("📸 사진 촬영 완료!")
        }

        // 5초 후 다시 촬영 가능
        DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) {
            capturedImage = nil
        }
    }

    // 이미지를 선택한 비율로 크롭
    private func cropImage(_ image: UIImage, to aspectRatio: CameraAspectRatio) -> UIImage {
        guard let cgImage = image.cgImage else { return image }

        let imageWidth = CGFloat(cgImage.width)
        let imageHeight = CGFloat(cgImage.height)
        let targetRatio = aspectRatio.ratio  // 가로:세로 비율 (예: 4:3 = 1.333)

        var cropRect: CGRect

        // fixedOrientation() 후의 이미지는 세로 모드
        // 세로 모드에서의 가로:세로 비율 계산
        let currentRatio = imageWidth / imageHeight  // 예: 3024 / 4032 = 0.75
        let targetVerticalRatio = 1.0 / targetRatio   // 예: 3/4 = 0.75

        if currentRatio > targetVerticalRatio {
            // 이미지가 목표보다 더 가로로 넓으면 (또는 덜 세로로 길면), 좌우를 크롭
            let targetWidth = imageHeight * targetVerticalRatio
            let xOffset = (imageWidth - targetWidth) / 2
            cropRect = CGRect(x: xOffset, y: 0, width: targetWidth, height: imageHeight)
        } else {
            // 이미지가 목표보다 더 세로로 길면, 위아래를 크롭
            let targetHeight = imageWidth / targetVerticalRatio
            let yOffset = (imageHeight - targetHeight) / 2
            cropRect = CGRect(x: 0, y: yOffset, width: imageWidth, height: targetHeight)
        }

        guard let croppedCGImage = cgImage.cropping(to: cropRect) else { return image }

        return UIImage(cgImage: croppedCGImage, scale: image.scale, orientation: image.imageOrientation)
    }

    // 🔧 사진을 올바른 방향으로 저장
    private func saveImageToPhotoLibrary(_ image: UIImage) {
        PHPhotoLibrary.requestAuthorization { status in
            guard status == .authorized else {
                print("⚠️ 사진 라이브러리 권한 없음")
                return
            }

            PHPhotoLibrary.shared().performChanges {
                // 이미지는 이미 CameraManager에서 fixedOrientation 처리됨
                let request = PHAssetChangeRequest.creationRequestForAsset(from: image)
                _ = request.placeholderForCreatedAsset
            } completionHandler: { success, error in
                if success {
                    print("✅ 사진 저장 성공")
                } else if let error = error {
                    print("❌ 사진 저장 실패: \(error.localizedDescription)")
                }
            }
        }
    }

    var body: some View {
        ZStack {
            // 1. 카메라 프리뷰 (비율에 따라 캡처 영역 표시)
            if cameraManager.isAuthorized {
                ZStack {
                    // 전체 화면 카메라 프리뷰
                    CameraView(cameraManager: cameraManager)
                        .ignoresSafeArea()

                    // 비율에 따른 마스크 오버레이 (캡처되지 않는 영역 어둡게)
                    AspectRatioMaskView(selectedRatio: selectedAspectRatio)
                        .ignoresSafeArea()
                        .allowsHitTesting(false)
                }
                .onAppear {
                    print("🎥🎥🎥 ContentView onAppear 호출됨 🎥🎥🎥")
                    debugAlert = true
                    cameraManager.setupSession()
                    cameraManager.startSession()
                    print("🎥🎥🎥 카메라 세션 시작 완료 🎥🎥🎥")
                }
                .onDisappear {
                    cameraManager.stopSession()
                    stopAnalysis()
                }
            } else {
                // 권한 없을 때
                VStack(spacing: 20) {
                    Image(systemName: "camera.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.gray)

                    Text("카메라 권한이 필요합니다")
                        .font(.title3)
                        .foregroundColor(.white)

                    Text("설정 > TryAngle > 카메라 허용")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
            }

            // 2. 그리드 오버레이
            if showGrid {
                GridOverlay()
                    .ignoresSafeArea()
            }

            // 3. 상단 툴바
            VStack {
                // 첫번째 행: 그리드, 플래시, 분석 모드
                HStack(spacing: 16) {
                    // 그리드 토글
                    Button(action: {
                        showGrid.toggle()
                    }) {
                        Image(systemName: showGrid ? "grid" : "grid.circle")
                            .font(.title3)
                            .foregroundColor(.white)
                            .frame(width: 44, height: 44)
                            .background(Color.black.opacity(0.5))
                            .clipShape(Circle())
                    }

                    // Flash 토글
                    Button(action: {
                        cameraManager.toggleFlash()
                    }) {
                        Image(systemName: cameraManager.isFlashOn ? "bolt.fill" : "bolt.slash.fill")
                            .font(.title3)
                            .foregroundColor(cameraManager.isFlashOn ? .yellow : .white)
                            .frame(width: 44, height: 44)
                            .background(Color.black.opacity(0.5))
                            .clipShape(Circle())
                    }

                    // 분석 모드 토글
                    Button(action: {
                        analysisEnabled.toggle()
                        if !analysisEnabled {
                            feedbackItems = []
                            processingTime = ""
                        }
                    }) {
                        Image(systemName: analysisEnabled ? "wand.and.stars" : "wand.and.stars.inverse")
                            .font(.title3)
                            .foregroundColor(analysisEnabled ? .cyan : .white)
                            .frame(width: 44, height: 44)
                            .background(Color.black.opacity(0.5))
                            .clipShape(Circle())
                    }

                    // 자동 촬영 토글
                    Button(action: {
                        autoCapture.toggle()
                    }) {
                        Image(systemName: autoCapture ? "camera.fill" : "camera")
                            .font(.title3)
                            .foregroundColor(autoCapture ? .yellow : .white)
                            .frame(width: 44, height: 44)
                            .background(Color.black.opacity(0.5))
                            .clipShape(Circle())
                    }

                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.top, 60)

                // 두번째 행: FPS 토글 및 비율 선택
                HStack(spacing: 16) {
                    // FPS 토글
                    Button(action: {
                        showFPS.toggle()
                    }) {
                        Image(systemName: showFPS ? "info.circle.fill" : "info.circle")
                            .font(.title3)
                            .foregroundColor(.white)
                            .frame(width: 44, height: 44)
                            .background(Color.black.opacity(0.5))
                            .clipShape(Circle())
                    }

                    // FPS 표시
                    if showFPS {
                        Text(String(format: "%.1f FPS", cameraManager.currentFPS))
                            .font(.caption)
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.black.opacity(0.6))
                            .cornerRadius(8)
                    }

                    Spacer()

                    // 🆕 비율 선택 버튼
                    Menu {
                        ForEach(CameraAspectRatio.allCases, id: \.self) { ratio in
                            Button(action: {
                                selectedAspectRatio = ratio
                            }) {
                                HStack {
                                    Text(ratio.displayName)
                                    if ratio == selectedAspectRatio {
                                        Image(systemName: "checkmark")
                                    }
                                }
                            }
                        }
                    } label: {
                        Text(selectedAspectRatio.displayName)
                            .font(.caption)
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.blue.opacity(0.7))
                            .cornerRadius(8)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)

                Spacer()
            }

            // 4. 피드백 오버레이 (실시간 + 서버 피드백 통합)
            FeedbackOverlay(
                feedbackItems: combinedFeedback,
                categoryStatuses: realtimeAnalyzer.categoryStatuses,  // 🆕 카테고리 상태 전달
                completedFeedbacks: realtimeAnalyzer.completedFeedbacks,  // 🆕 완료된 피드백 전달
                processingTime: processingTime
            )
            .onChange(of: realtimeAnalyzer.instantFeedback) { newFeedback in
                updateCombinedFeedback()
            }
            .onChange(of: serverFeedbackItems) { _ in
                updateCombinedFeedback()
            }

            // 레퍼런스 선택 안내
            if referenceImage == nil {
                VStack {
                    Spacer()
                        .frame(height: 200)

                    Text("📸 레퍼런스 이미지를 선택하세요")
                        .font(.title3)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 24)
                        .padding(.vertical, 16)
                        .background(Color.blue.opacity(0.8))
                        .cornerRadius(16)
                        .shadow(radius: 10)

                    Text("왼쪽 하단의 버튼을 눌러\n따라 찍고 싶은 사진을 선택하세요")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.8))
                        .multilineTextAlignment(.center)
                        .padding(.top, 8)

                    Spacer()
                }
            }

            // 완벽한 상태 표시 (레퍼런스가 있을 때만)
            else if referenceImage != nil && realtimeAnalyzer.isPerfect {
                VStack {
                    Spacer()
                        .frame(height: 200)

                    HStack {
                        Spacer()
                        VStack(spacing: 16) {
                            // 완벽 표시
                            ZStack {
                                Circle()
                                    .fill(Color.green.opacity(0.9))
                                    .frame(width: 100, height: 100)
                                    .overlay(
                                        Circle()
                                            .stroke(Color.white, lineWidth: 4)
                                    )

                                VStack(spacing: 4) {
                                    Image(systemName: "checkmark")
                                        .font(.system(size: 40, weight: .bold))
                                        .foregroundColor(.white)
                                    Text("완벽!")
                                        .font(.headline)
                                        .foregroundColor(.white)
                                }
                            }
                            .scaleEffect(showCaptureFlash ? 1.2 : 1.0)
                            .animation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true), value: showCaptureFlash)

                            // 자동 촬영 카운트다운
                            if autoCapture {
                                Text("자동 촬영!")
                                    .font(.caption)
                                    .foregroundColor(.white)
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 8)
                                    .background(Color.green.opacity(0.8))
                                    .cornerRadius(20)
                            }
                        }
                        Spacer()
                    }

                    Spacer()
                }
            }

            // 촬영 플래시 효과
            if showCaptureFlash {
                Color.white
                    .ignoresSafeArea()
                    .opacity(0.8)
                    .transition(.opacity)
            }

            // 완성도 점수 표시 (디버깅용)
            if showFPS {
                VStack {
                    HStack {
                        Spacer()
                        Text(String(format: "완성도: %.0f%%", realtimeAnalyzer.perfectScore * 100))
                            .font(.caption)
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.blue.opacity(0.6))
                            .cornerRadius(8)
                            .padding(.trailing, 16)
                    }
                    .padding(.top, 200)
                    Spacer()
                }
            }

            // 5. 하단 컨트롤
            VStack {
                Spacer()

                HStack(alignment: .center, spacing: 20) {
                    // 레퍼런스 선택
                    ReferenceSelector(selectedImage: $referenceImage)
                        .onChange(of: referenceImage) { newImage in
                            if let image = newImage {
                                // 레퍼런스 분석
                                realtimeAnalyzer.analyzeReference(image)
                                startRealtimeAnalysis()  // 실시간 분석 시작
                                startAnalysis()          // 서버 분석도 병행 (포즈용)
                            } else {
                                stopRealtimeAnalysis()
                                stopAnalysis()
                            }
                        }

                    Spacer()

                    // 촬영 버튼 (중앙)
                    Button(action: {
                        performCapture()
                    }) {
                        ZStack {
                            Circle()
                                .fill(Color.white)
                                .frame(width: 70, height: 70)

                            Circle()
                                .stroke(Color.white, lineWidth: 3)
                                .frame(width: 82, height: 82)

                            if capturedImage != nil {
                                Image(systemName: "checkmark")
                                    .font(.title)
                                    .foregroundColor(.green)
                            }
                        }
                    }
                    .disabled(capturedImage != nil)
                    .opacity(capturedImage != nil ? 0.5 : 1.0)

                    Spacer()

                    // 카메라 전환 버튼
                    Button(action: {
                        cameraManager.switchCamera()
                    }) {
                        Image(systemName: "camera.rotate")
                            .font(.title2)
                            .foregroundColor(.white)
                            .frame(width: 50, height: 50)
                            .background(Color.black.opacity(0.6))
                            .clipShape(Circle())
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 40)
            }

            // 4. 에러 메시지
            if let error = errorMessage {
                VStack {
                    Text("⚠️ \(error)")
                        .font(.caption)
                        .foregroundColor(.white)
                        .padding()
                        .background(Color.red.opacity(0.8))
                        .cornerRadius(8)
                        .padding(.top, 100)

                    Spacer()
                }
            }

            // 5. 분석 중 인디케이터
            if isAnalyzing {
                VStack {
                    HStack {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        Text("분석 중...")
                            .font(.caption)
                            .foregroundColor(.white)
                    }
                    .padding()
                    .background(Color.black.opacity(0.7))
                    .cornerRadius(8)
                    .padding(.top, 100)

                    Spacer()
                }
            }

            // 🐛 디버그 오버레이 (포즈 감지 상태 표시)
            VStack {
                Spacer()
                HStack {
                    Spacer()
                    VStack(alignment: .trailing, spacing: 4) {
                        // 레퍼런스 포즈 키포인트
                        if let refPose = realtimeAnalyzer.referenceAnalysis?.poseKeypoints {
                            let visibleCount = refPose.filter { $0.confidence >= 0.5 }.count
                            let color: Color = visibleCount >= 10 ? .green : (visibleCount >= 5 ? .yellow : .red)
                            Text("레퍼런스: \(visibleCount)/\(refPose.count)개")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(color)
                                .padding(4)
                                .background(Color.black.opacity(0.7))
                                .cornerRadius(4)
                        } else {
                            Text("레퍼런스 포즈: 없음 ⚠️")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(.red)
                                .padding(4)
                                .background(Color.black.opacity(0.7))
                                .cornerRadius(4)
                        }

                        // 현재 프레임의 포즈 피드백 표시
                        let poseFeedbacks = combinedFeedback.filter { $0.icon == "💪" }
                        if !poseFeedbacks.isEmpty {
                            Text("포즈 피드백: \(poseFeedbacks.count)개")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(.orange)
                                .padding(4)
                                .background(Color.black.opacity(0.7))
                                .cornerRadius(4)
                        } else if referenceImage != nil {
                            // 레퍼런스 포즈가 있을 때만 "일치" 표시
                            if let refPose = realtimeAnalyzer.referenceAnalysis?.poseKeypoints,
                               refPose.filter({ $0.confidence >= 0.5 }).count >= 5 {
                                Text("포즈: 일치 ✓")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundColor(.green)
                                    .padding(4)
                                    .background(Color.black.opacity(0.7))
                                    .cornerRadius(4)
                            } else {
                                Text("포즈: 비교 불가")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundColor(.gray)
                                    .padding(4)
                                    .background(Color.black.opacity(0.7))
                                    .cornerRadius(4)
                            }
                        }

                        // 완성도 표시
                        if referenceImage != nil {
                            let score = Int(realtimeAnalyzer.perfectScore * 100)
                            Text("완성도: \(score)%")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(score > 100 ? .red : .white)
                                .padding(4)
                                .background(Color.black.opacity(0.7))
                                .cornerRadius(4)
                        }
                    }
                    .padding(.trailing, 8)
                    .padding(.bottom, 120)
                }
            }
        }
        .onChange(of: realtimeAnalyzer.isPerfect) { isPerfect in
            if isPerfect && autoCapture && capturedImage == nil {
                performCapture()
            }
        }
        .onChange(of: selectedAspectRatio) { newRatio in
            cameraManager.setAspectRatio(newRatio)

            // 비율 변경시 즉시 프레임 재분석하여 피드백 갱신
            if let currentFrame = cameraManager.currentFrame {
                realtimeAnalyzer.analyzeFrame(currentFrame, isFrontCamera: cameraManager.isFrontCamera)
            }
        }
        .alert("앱 초기화 완료", isPresented: $debugAlert) {
            Button("확인") { }
        } message: {
            Text("ContentView가 정상적으로 로드되었습니다.\n\n디버그 로그:\n1. Xcode 콘솔 확인\n2. /tmp/xcode_console_fix.txt 참고\n3. Documents/pose_debug.txt 파일 확인\n\n오른쪽 하단에서 포즈 감지 상태를 실시간으로 확인할 수 있습니다.")
        }
    }

    // MARK: - Analysis Control

    /// 실시간 프레임 분석 시작 (클라이언트 사이드)
    private func startRealtimeAnalysis() {
        // 기존 타이머 중지
        stopRealtimeAnalysis()

        // 🔄 10fps로 프레임 분석 (100ms마다) - 민감도 감소
        frameUpdateTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { _ in
            if let currentFrame = cameraManager.currentFrame {
                realtimeAnalyzer.analyzeFrame(currentFrame, isFrontCamera: cameraManager.isFrontCamera)
            }
        }
    }

    /// 실시간 분석 중지
    private func stopRealtimeAnalysis() {
        frameUpdateTimer?.invalidate()
        frameUpdateTimer = nil
        realtimeAnalyzer.instantFeedback = []
    }

    /// 서버 분석 시작 (포즈 등 복잡한 분석용)
    private func startAnalysis() {
        guard referenceImage != nil else { return }

        // 기존 타이머 중지
        stopAnalysis()

        // 2초마다 서버 분석 (포즈만)
        analysisTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            Task {
                await performAnalysis()
            }
        }
    }

    /// 서버 분석 중지
    private func stopAnalysis() {
        analysisTimer?.invalidate()
        analysisTimer = nil
        serverFeedbackItems = []
        processingTime = ""
    }

    /// 실제 분석 수행 (V1: 온디바이스만 사용, 서버 연결 비활성화)
    private func performAnalysis() async {
        // 분석 모드가 꺼져있으면 스킵
        guard analysisEnabled else {
            return
        }

        // 이미 분석 중이면 스킵 (중복 요청 방지)
        guard !isAnalyzing else {
            print("⏭️ 이전 분석이 진행 중이므로 스킵")
            return
        }

        guard referenceImage != nil,
              cameraManager.currentFrame != nil else {
            return
        }

        isAnalyzing = true
        errorMessage = nil

        // V1: 온디바이스 분석만 사용 (서버 연결 안 함)
        // RealtimeAnalyzer가 모든 분석을 처리함 (YOLO + MoveNet + Vision)
        // serverFeedbackItems는 사용하지 않음 (combinedFeedback에서 realtimeAnalyzer.instantFeedback만 사용)

        await MainActor.run {
            serverFeedbackItems = []  // 서버 피드백 비우기
            processingTime = "On-Device"  // 온디바이스 표시
            isAnalyzing = false
        }
    }
}

// MARK: - Aspect Ratio Mask View

struct AspectRatioMaskView: View {
    let selectedRatio: CameraAspectRatio

    var body: some View {
        GeometryReader { geometry in
            let screenWidth = geometry.size.width
            let screenHeight = geometry.size.height

            // 실제 iPhone 카메라처럼: 4:3이 기본(전체 화면), 나머지는 위아래 크롭
            // iPhone 화면 비율은 대략 19.5:9 (2.16:1)

            let captureHeight: CGFloat = {
                switch selectedRatio {
                case .ratio4_3:
                    // 4:3 - 세로 모드에서 4:3 비율 (width x width*4/3)
                    // iPhone 카메라 센서의 기본 비율 (가로:세로 = 4:3)
                    // 세로 모드에서는 너비를 기준으로 높이 계산
                    return screenWidth * 4.0 / 3.0

                case .ratio1_1:
                    // 1:1 - 정사각형, 너비를 기준으로 높이 설정
                    return screenWidth

                case .ratio16_9:
                    // 16:9 - 와이드, 가장 좁은 높이
                    return screenWidth * 16.0 / 9.0
                }
            }()

            // 위아래 마스크 높이 계산
            let maskHeight = max(0, (screenHeight - captureHeight) / 2)

            ZStack {
                if maskHeight > 0 {
                    // 상단 마스크
                    VStack {
                        Rectangle()
                            .fill(Color.black.opacity(0.7))
                            .frame(height: maskHeight)
                        Spacer()
                    }

                    // 하단 마스크
                    VStack {
                        Spacer()
                        Rectangle()
                            .fill(Color.black.opacity(0.7))
                            .frame(height: maskHeight)
                    }
                }
            }
            .ignoresSafeArea()
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
