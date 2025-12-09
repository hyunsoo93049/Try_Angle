import Foundation
import Vision
import UIKit
import CoreImage
import Combine

// MARK: - v1.5 Extension for DepthResult
extension DepthResult {
    /// v1.5 호환: 압축감 지수 계산 (거리 및 줌 기반)
    var compressionIndex: Float {
        // 줌 배율에 따른 압축감 추정
        let zoom = zoomFactor ?? 1.0
        if zoom >= 3.0 {
            return 0.8  // 망원
        } else if zoom >= 2.0 {
            return 0.6  // 준망원
        } else if zoom <= 0.6 {
            return 0.2  // 광각
        } else {
            return 0.4  // 표준
        }
    }
}

// MARK: - 실시간 분석을 위한 데이터 구조
struct FrameAnalysis {
    let faceRect: CGRect?                           // 얼굴 위치 (정규화된 좌표)
    let bodyRect: CGRect?                           // 전신 추정 영역
    let brightness: Float                           // 평균 밝기
    let tiltAngle: Float                            // 기울기 각도
    let faceYaw: Float?                             // 얼굴 좌우 회전 (정면=0)
    let facePitch: Float?                           // 얼굴 상하 각도
    let cameraAngle: CameraAngle                    // 카메라 각도
    let poseKeypoints: [(point: CGPoint, confidence: Float)]?  // 신뢰도 포함 키포인트
    let compositionType: CompositionType?           // 구도 타입
    let faceObservation: VNFaceObservation?         // 얼굴 관찰 결과
    let gaze: GazeResult?                           // 🆕 시선 추적 결과
    let depth: DepthResult?                         // 🆕 깊이 추정 결과
    let aspectRatio: CameraAspectRatio              // 🆕 카메라 비율
    let imagePadding: ImagePadding?                 // 🆕 여백 정보
}

// 🆕 이미지 여백 정보
struct ImagePadding {
    let top: CGFloat        // 상단 여백 (0.0 ~ 1.0)
    let bottom: CGFloat     // 하단 여백
    let left: CGFloat       // 좌측 여백
    let right: CGFloat      // 우측 여백

    var total: CGFloat {
        return top + bottom + left + right
    }

    var hasExcessivePadding: Bool {
        // 어느 한 쪽이 15% 이상 여백이면 과도함
        return top > 0.15 || bottom > 0.15 || left > 0.15 || right > 0.15
    }
}

// MARK: - 실시간 피드백 생성기
class RealtimeAnalyzer: ObservableObject {
    @Published var instantFeedback: [FeedbackItem] = []
    @Published var isPerfect: Bool = false  // 완벽한 상태 감지
    @Published var perfectScore: Double = 0.0  // 완성도 점수 (0~1)
    @Published var categoryStatuses: [CategoryStatus] = []  // 🆕 카테고리별 상태
    @Published var completedFeedbacks: [CompletedFeedback] = []  // 🆕 완료된 피드백들

    // 🆕 v1.5 Gate System 결과
    @Published var gateEvaluation: GateEvaluation?
    @Published var v15Feedback: String = ""  // v1.5 피드백 메시지

    // 🆕 v1.5 통합 피드백 (하나의 동작 → 여러 Gate 해결)
    @Published var unifiedFeedback: UnifiedFeedback?

    // 🐛 ContentView에서 접근 가능하도록 internal로 변경
    var referenceAnalysis: FrameAnalysis?
    var referenceFramingResult: PhotographyFramingResult?  // 🆕 레퍼런스 사진학 프레이밍 분석 결과

    // 🆕 v1.5 캐시된 레퍼런스
    var cachedReference: CachedReference?

    private var lastAnalysisTime = Date()
    private let analysisInterval: TimeInterval = 0.05  // 50ms마다 분석 - 반응속도 개선

    // 🔥 분석 전용 백그라운드 큐 (UI 블로킹 방지)
    private let analysisQueue = DispatchQueue(label: "com.tryangle.analysis", qos: .userInitiated)
    private var isAnalyzing = false  // 분석 중복 방지 플래그

    // 히스테리시스를 위한 상태 추적
    private var feedbackHistory: [String: Int] = [:]  // 카테고리별 연속 감지 횟수
    private let historyThreshold = 3  // 🔄 3번 연속 감지되어야 표시 (약 0.3초) - 반응속도 개선
    private var perfectFrameCount = 0  // 완벽한 프레임 연속 횟수
    private let perfectThreshold = 5  // 5프레임(약 0.5초) 연속 완벽해야 감지 - 반응속도 개선

    // 🆕 고정 피드백 (한 번 표시되면 해결될 때까지 유지)
    private var stickyFeedbacks: [String: FeedbackItem] = [:]  // 카테고리별 고정 피드백

    // 🆕 이전 프레임의 피드백 (완료 감지용)
    private var previousFeedbackIds = Set<String>()
    // 🆕 완료 감지를 위한 히스테리시스
    private var disappearedFeedbackHistory: [String: Int] = [:]  // 사라진 피드백의 연속 횟수
    private let disappearedThreshold = 2  // 2번 연속 사라져야 완료로 판단 - 반응속도 개선

    // 🆕 고정 피드백 카테고리 (포즈 관련은 계속 표시)
    // pose_missing_parts는 이제 레퍼런스 기반으로 제대로 감지되므로 sticky 처리
    private let stickyCategories: Set<String> = [
        "pose_left_arm",
        "pose_right_arm",
        "pose_left_leg",
        "pose_right_leg",
        "pose_missing_parts"
    ]

    // 🔥 RTMPose 분석기 (ONNX Runtime with CoreML EP)
    private var poseMLAnalyzer: PoseMLAnalyzer!
    private let compositionAnalyzer = CompositionAnalyzer()
    private let cameraAngleDetector = CameraAngleDetector()
    private let gazeTracker = GazeTracker()
    private let depthEstimator = DepthEstimator()
    private let poseComparator = AdaptivePoseComparator()
    private let gapAnalyzer = GapAnalyzer()
    private let feedbackGenerator = FeedbackGenerator()  // 🗑️ 구식 (레거시 호환용)
    private let framingAnalyzer = FramingAnalyzer()  // 기존 프레이밍 분석기
    private let photographyFramingAnalyzer = PhotographyFramingAnalyzer()  // 사진학 기반 프레이밍 분석기
    // 🗑️ stagedFeedbackGenerator 삭제 - Gate System으로 통합됨

    // 🆕 v1.5 통합 Gate System (5단계)
    private let gateSystem = GateSystem.shared
    private let marginAnalyzer = MarginAnalyzer()
    private let personDetector = PersonDetector()  // 정밀 BBox (30프레임마다)
    private let focalLengthEstimator = FocalLengthEstimator.shared  // 🆕 35mm 환산 초점거리

    // 🆕 v1.5 프레임 카운터 (Level 처리용)
    private var frameCount = 0
    private var lastGroundingDINOBBox: CGRect?  // 마지막 Grounding DINO 결과 캐시
    private var lastCompressionIndex: CGFloat?  // 마지막 압축감 캐시
    private var lastDepthResult: DepthResult?   // 마지막 Depth 결과 캐시 (Level 2)

    // 🆕 35mm 환산 초점거리 관련
    private var referenceImageData: Data?       // 레퍼런스 EXIF 추출용
    private var referenceDepthMap: MLMultiArray?  // 레퍼런스 뎁스맵 (EXIF 없을 때 fallback)
    private var referenceFocalLength: FocalLengthInfo?  // 캐시된 레퍼런스 초점거리
    var currentZoomFactor: CGFloat = 1.0        // 현재 줌 배율 (CameraManager에서 업데이트)

    // 🔥 성능 최적화
    private let thermalManager = ThermalStateManager()
    private let frameSkipper = AdaptiveFrameSkipper()
    private var lastPerformanceLog = Date()

    // 🆕 초기화
    init() {
        print("🎬🎬🎬 RealtimeAnalyzer init() 호출됨 🎬🎬🎬")

        // 🔥 PoseMLAnalyzer를 백그라운드에서 미리 로드 (앱 시작 시 17초 지연 방지)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            print("🔥 RealtimeAnalyzer: PoseMLAnalyzer 백그라운드 초기화 시작")
            let startTime = CACurrentMediaTime()
            let analyzer = PoseMLAnalyzer()
            let loadTime = (CACurrentMediaTime() - startTime) * 1000
            print("✅ RealtimeAnalyzer: PoseMLAnalyzer 초기화 완료 (\(String(format: "%.0f", loadTime))ms)")

            DispatchQueue.main.async {
                self?.poseMLAnalyzer = analyzer
            }
        }
    }

    // Vision 요청 캐싱
    private lazy var faceDetectionRequest: VNDetectFaceLandmarksRequest = {
        let request = VNDetectFaceLandmarksRequest()
        request.revision = VNDetectFaceLandmarksRequestRevision3
        return request
    }()

    private lazy var poseDetectionRequest: VNDetectHumanBodyPoseRequest = {
        let request = VNDetectHumanBodyPoseRequest()
        return request
    }()

    // MARK: - Helper Methods

    /// 여백 계산 (RTMPose 구조적 키포인트 기반)
    private func calculatePaddingFromKeypoints(
        keypoints: [(point: CGPoint, confidence: Float)]
    ) -> ImagePadding? {
        // 구조적 키포인트만 사용 (0-16: 몸통 키포인트, 손가락/얼굴 랜드마크 제외)
        let structuralIndices = PhotographyFramingAnalyzer.StructuralKeypoints.all

        // 신뢰도 0.3 이상인 키포인트만 필터링
        let validPoints = structuralIndices.compactMap { idx -> CGPoint? in
            guard idx < keypoints.count else { return nil }
            return keypoints[idx].confidence > 0.3 ? keypoints[idx].point : nil
        }

        // 최소 3개 이상의 키포인트가 필요
        guard validPoints.count >= 3 else { return nil }

        // 바운딩 박스 계산 (정규화된 좌표: 0.0 ~ 1.0)
        let minX = validPoints.map { $0.x }.min() ?? 0
        let maxX = validPoints.map { $0.x }.max() ?? 1
        let minY = validPoints.map { $0.y }.min() ?? 0
        let maxY = validPoints.map { $0.y }.max() ?? 1

        // 여백 계산 (정규화된 좌표계)
        let top = 1.0 - maxY     // 상단 여백
        let bottom = minY        // 하단 여백
        let left = minX          // 좌측 여백
        let right = 1.0 - maxX   // 우측 여백

        return ImagePadding(
            top: top,
            bottom: bottom,
            left: left,
            right: right
        )
    }

    /// 🗑️ 구식 여백 계산 (얼굴 위치 기반 bodyRect 추정) - 더 이상 사용 안함
    @available(*, deprecated, message: "Use calculatePaddingFromKeypoints instead")
    private func calculatePadding(bodyRect: CGRect?, imageSize: CGSize) -> ImagePadding? {
        guard let body = bodyRect else { return nil }

        // 🔥 Vision 좌표계: Y=0(화면 하단), Y=1(화면 상단)
        // body.minY = 인물의 아래쪽 경계 (Y 작은 값)
        // body.maxY = 인물의 위쪽 경계 (Y 큰 값)

        let top = 1.0 - body.maxY  // 화면 상단 여백 (인물 위 공간)
        let bottom = body.minY     // 화면 하단 여백 (인물 아래 공간)
        let left = body.minX       // 좌측 여백
        let right = 1.0 - body.maxX  // 우측 여백

        return ImagePadding(
            top: top,
            bottom: bottom,
            left: left,
            right: right
        )
    }

    /// 🆕 v6: 키포인트에서 인물 바운딩 박스 계산 (Python improved_margin_analyzer._calculate_person_bbox 이식)
    /// - Returns: 정규화된 좌표 (0.0 ~ 1.0)의 바운딩 박스
    private func calculateBodyRectFromKeypoints(_ keypoints: [(point: CGPoint, confidence: Float)], imageSize: CGSize) -> CGRect? {
        // 신뢰도 0.3 이상인 구조적 키포인트(0-16)만 필터링
        let structuralIndices = PhotographyFramingAnalyzer.StructuralKeypoints.all

        let validPoints = structuralIndices.compactMap { idx -> CGPoint? in
            guard idx < keypoints.count else { return nil }
            return keypoints[idx].confidence > 0.3 ? keypoints[idx].point : nil
        }

        // 최소 3개 이상의 키포인트가 필요
        guard validPoints.count >= 3 else { return nil }

        // 바운딩 박스 계산 (픽셀 좌표)
        let minX = validPoints.map { $0.x }.min() ?? 0
        let maxX = validPoints.map { $0.x }.max() ?? 1
        let minY = validPoints.map { $0.y }.min() ?? 0
        let maxY = validPoints.map { $0.y }.max() ?? 1

        // 🆕 정규화 (0.0 ~ 1.0)
        let normalizedX = minX / imageSize.width
        let normalizedY = minY / imageSize.height
        let normalizedWidth = (maxX - minX) / imageSize.width
        let normalizedHeight = (maxY - minY) / imageSize.height

        return CGRect(x: normalizedX, y: normalizedY, width: normalizedWidth, height: normalizedHeight)
    }

    // MARK: - 레퍼런스 이미지 분석
    func analyzeReference(_ image: UIImage, imageData: Data? = nil) {
        print("========================================")
        print("🎯🎯🎯 레퍼런스 이미지 분석 시작 🎯🎯🎯")
        print("========================================")

        // 🆕 EXIF 추출용 이미지 데이터 저장
        self.referenceImageData = imageData ?? image.jpegData(compressionQuality: 1.0)

        guard let cgImage = image.cgImage else {
            print("❌ cgImage 없음")
            return
        }

        // 🆕 모델 로딩 대기
        guard let analyzer = poseMLAnalyzer else {
            print("⏳ PoseMLAnalyzer 로딩 중... 레퍼런스 분석 대기")
            // 0.5초 후 재시도
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                self?.analyzeReference(image)
            }
            return
        }

        print("🎯 레퍼런스 이미지 크기: \(cgImage.width) x \(cgImage.height)")
        print("🎯 레퍼런스 이미지 orientation: \(image.imageOrientation.rawValue)")

        // 🔥 RTMPose로 얼굴+포즈 동시 분석 (ONNX Runtime with CoreML EP)
        print("🎯 PoseMLAnalyzer.analyzeFaceAndPose() 호출 중...")
        let (faceResult, poseResult) = analyzer.analyzeFaceAndPose(from: image)
        print("🎯 분석 완료:")
        print("   - 얼굴: \(faceResult != nil ? "✅ 검출됨" : "❌ 검출 안됨")")
        print("   - 포즈: \(poseResult != nil ? "✅ 검출됨 (\(poseResult!.keypoints.count)개 키포인트)" : "❌ 검출 안됨")")

        if let pose = poseResult {
            let visibleCount = pose.keypoints.filter { $0.confidence >= 0.5 }.count
            print("   - 포즈 신뢰도 ≥ 0.5: \(visibleCount)/\(pose.keypoints.count)개")
        }

        // 🔥 디버그: 포즈 검출 실패 시 이미지 저장
        if poseResult == nil {
            saveDebugImage(image, reason: "pose_detection_failed")
        }

        let faceRect = faceResult?.faceRect
        let faceYaw = faceResult?.yaw
        let facePitch = faceResult?.pitch
        let poseKeypoints = poseResult?.keypoints

        // 밝기 계산
        let brightness = poseMLAnalyzer.calculateBrightness(from: cgImage)

        // 🆕 더치 틸트 감지
        let tiltAngle = cameraAngleDetector.detectDutchTilt(faceObservation: faceResult?.observation) ?? 0.0

        // 전신 영역 추정
        let bodyRect = poseMLAnalyzer.estimateBodyRect(from: faceRect)

        // 카메라 앵글 감지
        let cameraAngle = cameraAngleDetector.detectCameraAngle(
            faceRect: faceRect,
            facePitch: facePitch,
            faceObservation: faceResult?.observation
        )

        // 구도 타입 분류
        var compositionType: CompositionType? = nil
        if let faceRect = faceRect {
            let subjectPosition = CGPoint(x: faceRect.midX, y: faceRect.midY)
            compositionType = compositionAnalyzer.classifyComposition(subjectPosition: subjectPosition)
        }

        // 🆕 시선 추적
        var gaze: GazeResult? = nil
        if let faceObservation = faceResult?.observation {
            gaze = gazeTracker.trackGaze(from: faceObservation)
        }

        // 🆕 깊이 추정
        var depth: DepthResult? = nil
        if let faceRect = faceRect {
            depth = depthEstimator.estimateDistance(
                faceRect: faceRect,
                imageWidth: cgImage.width,
                zoomFactor: 1.0  // TODO: CameraManager에서 실제 줌 값 가져오기
            )
        }

        // 🆕 비율 감지
        let imageSize = CGSize(width: cgImage.width, height: cgImage.height)
        let aspectRatio = CameraAspectRatio.detect(from: imageSize)

        // 🆕 여백 계산 (RTMPose 키포인트 기반)
        var padding: ImagePadding? = nil
        if let keypoints = poseKeypoints, keypoints.count >= 17 {
            // 키포인트를 정규화된 좌표로 변환 (0.0 ~ 1.0)
            let normalizedKeypoints = keypoints.map { kp -> (point: CGPoint, confidence: Float) in
                let normalizedPoint = CGPoint(
                    x: kp.point.x / imageSize.width,
                    y: kp.point.y / imageSize.height
                )
                return (point: normalizedPoint, confidence: kp.confidence)
            }
            // 구조적 키포인트(0-16)로 여백 계산
            padding = calculatePaddingFromKeypoints(keypoints: normalizedKeypoints)
        }

        // 🆕 사진학 기반 프레이밍 분석 (RTMPose 133개 키포인트)
        if let keypoints = poseKeypoints, keypoints.count >= 133 {
            let normalizedKeypoints = keypoints.map { kp -> (point: CGPoint, confidence: Float) in
                let normalizedPoint = CGPoint(
                    x: kp.point.x / imageSize.width,
                    y: kp.point.y / imageSize.height
                )
                return (point: normalizedPoint, confidence: kp.confidence)
            }
            referenceFramingResult = photographyFramingAnalyzer.analyze(
                keypoints: normalizedKeypoints,
                imageSize: imageSize
            )
            if let refFraming = referenceFramingResult {
                print("   - 📸 레퍼런스 샷 타입: \(refFraming.shotType.rawValue)")
                print("   - 📸 레퍼런스 헤드룸: \(String(format: "%.1f%%", refFraming.headroom * 100))")
                print("   - 📸 레퍼런스 카메라 앵글: \(refFraming.cameraAngle.rawValue)")
            }
        } else {
            referenceFramingResult = nil
            print("   - ⚠️ 사진학 프레이밍 분석 불가 (키포인트 부족)")
        }

        referenceAnalysis = FrameAnalysis(
            faceRect: faceRect,
            bodyRect: bodyRect,
            brightness: brightness,
            tiltAngle: tiltAngle,
            faceYaw: faceYaw,
            facePitch: facePitch,
            cameraAngle: cameraAngle,
            poseKeypoints: poseKeypoints,
            compositionType: compositionType,
            faceObservation: faceResult?.observation,
            gaze: gaze,
            depth: depth,
            aspectRatio: aspectRatio,
            imagePadding: padding
        )

        // 🆕 v1.5: Grounding DINO로 정밀 BBox 분석
        var preciseBBox: CGRect?
        if let ciImage = CIImage(image: image) {
            let semaphore = DispatchSemaphore(value: 0)
            personDetector.detectPerson(in: ciImage) { bbox in
                preciseBBox = bbox
                semaphore.signal()
            }
            semaphore.wait()
        }

        // 🆕 v1.5: 여백 분석 및 캐싱
        if let bbox = preciseBBox ?? bodyRect {
            let marginResult = marginAnalyzer.analyze(
                bbox: bbox,
                imageSize: imageSize,
                isNormalized: true
            )

            // 캐시 저장
            let refId = UUID().uuidString
            cachedReference = CacheManager.shared.cacheReference(
                id: refId,
                image: image,
                bbox: bbox,
                margins: marginResult,
                compressionIndex: depth.map { CGFloat($0.compressionIndex) }
            )
            print("📦 v1.5 레퍼런스 캐시 완료: \(refId)")
        }

        // 🆕 35mm 환산 초점거리 추정 (EXIF → 뎁스맵 순서)
        // TODO: Depth Anything V2 CoreML로 뎁스맵 생성 후 저장
        // 현재는 EXIF 우선, fallback으로 기본값 사용
        self.referenceFocalLength = focalLengthEstimator.estimateReferenceFocalLength(
            imageData: referenceImageData,
            depthMap: referenceDepthMap,  // TODO: 실제 뎁스맵 연동
            fallback: 50  // 핸드폰 사진 기본값 (표준 렌즈 추정)
        )

        if let refFL = referenceFocalLength {
            print("📐 레퍼런스 초점거리: \(refFL.focalLength35mm)mm (\(refFL.lensType.displayName)) - \(refFL.source.description)")
        }

        print("========================================")
        print("📸 레퍼런스 분석 최종 결과:")
        print("========================================")
        print("   - 비율: \(aspectRatio.displayName)")
        print("   - 얼굴: \(faceRect != nil ? "✅ 감지됨" : "❌ 없음")")
        print("   - 얼굴 각도: yaw=\(faceYaw ?? 0), pitch=\(facePitch ?? 0)")
        print("   - 카메라 앵글: \(cameraAngle.description)")
        print("   - 구도: \(compositionType?.description ?? "알 수 없음")")
        print("   - 시선: \(gaze?.direction.description ?? "알 수 없음")")
        print("   - 거리: \(depth?.distance.map { String(format: "%.2fm", $0) } ?? "알 수 없음")")
        print("   - 🆕 Grounding DINO BBox: \(preciseBBox != nil ? "✅" : "❌ (RTMPose 사용)")")

        if let keypoints = poseKeypoints {
            let visibleCount = keypoints.filter { $0.confidence >= 0.5 }.count
            print("   - 포즈 키포인트: \(keypoints.count)개 (신뢰도 ≥ 0.5: \(visibleCount)개)")
            if visibleCount >= 5 {
                print("   - ✅ 포즈 검출 성공! UI에 표시될 것임")
            } else {
                print("   - ⚠️ 포즈 신뢰도 낮음 - 포즈 비교 불가능")
            }
        } else {
            print("   - ❌ 포즈 키포인트: 없음")
            print("   - ⚠️ RTMPose 포즈 검출 실패")
        }

        print("   - 밝기: \(brightness)")
        print("   - 기울기: \(tiltAngle)도")
        print("========================================")
    }

    // MARK: - 실시간 프레임 분석
    func analyzeFrame(_ image: UIImage, isFrontCamera: Bool = false, currentAspectRatio: CameraAspectRatio = .ratio4_3) {
        // 🔥 동적 분석 간격 (발열 상태에 따라 조절)
        let dynamicInterval = thermalManager.recommendedAnalysisInterval
        guard Date().timeIntervalSince(lastAnalysisTime) >= dynamicInterval else { return }

        // 이미 분석 중이면 스킵 (UI 블로킹 방지)
        guard !isAnalyzing else { return }

        // 레퍼런스가 없으면 분석하지 않음
        guard let reference = referenceAnalysis else {
            DispatchQueue.main.async {
                self.instantFeedback = []
                self.perfectScore = 0.0
                self.isPerfect = false
            }
            return
        }

        guard let cgImage = image.cgImage else { return }
        lastAnalysisTime = Date()
        isAnalyzing = true

        // 🔥 백그라운드 큐에서 분석 실행 (UI 블로킹 방지)
        analysisQueue.async { [weak self] in
            guard let self = self else { return }

            // 🆕 모델 로딩 대기 (앱 시작 직후)
            guard let analyzer = self.poseMLAnalyzer else {
                print("⏳ PoseMLAnalyzer 로딩 중... 분석 스킵")
                DispatchQueue.main.async {
                    self.isAnalyzing = false
                }
                return
            }

            let analysisStart = CACurrentMediaTime()  // 🔍 프로파일링

            // RTMPose로 분석 (ONNX Runtime with CoreML EP)
            let poseStart = CACurrentMediaTime()  // 🔍
            let (faceResult, poseResult) = analyzer.analyzeFaceAndPose(from: image)
            let poseEnd = CACurrentMediaTime()  // 🔍

            let analysisEnd = CACurrentMediaTime()  // 🔍

            // 🔍 프로파일링 로그 (매 분석마다)
            let poseTime = (poseEnd - poseStart) * 1000
            let totalTime = (analysisEnd - analysisStart) * 1000
            print("📊 [RealtimeAnalyzer] RTMPose: \(String(format: "%.1f", poseTime))ms, 총분석: \(String(format: "%.1f", totalTime))ms")

            // 분석 완료 후 메인 스레드에서 UI 업데이트
            DispatchQueue.main.async {
                self.isAnalyzing = false
                self.processAnalysisResult(
                    faceResult: faceResult,
                    poseResult: poseResult,
                    cgImage: cgImage,
                    reference: reference,
                    isFrontCamera: isFrontCamera,
                    currentAspectRatio: currentAspectRatio
                )
            }
        }
    }

    // MARK: - 분석 결과 처리 (메인 스레드)
    private func processAnalysisResult(
        faceResult: FaceAnalysisResult?,
        poseResult: PoseAnalysisResult?,
        cgImage: CGImage,
        reference: FrameAnalysis,
        isFrontCamera: Bool,
        currentAspectRatio: CameraAspectRatio
    ) {
        // 🆕 v1.5: 프레임 카운터 증가
        frameCount += 1

        // 🔥 성능 로그 (10초마다)
        if Date().timeIntervalSince(lastPerformanceLog) >= 10 {
            lastPerformanceLog = Date()
            print(PerformanceOptimizer.shared.getPerformanceReport())
            print("🌡️ 발열 상태: \(thermalManager.currentThermalState.rawValue), 분석 간격: \(Int(thermalManager.recommendedAnalysisInterval * 1000))ms")
        }

        // 얼굴이 감지되지 않으면 완성도 0으로 설정
        guard faceResult != nil else {
            self.instantFeedback = [FeedbackItem(
                priority: 1,
                icon: "👤",
                message: "얼굴을 화면에 보여주세요",
                category: "no_face",
                currentValue: nil,
                targetValue: nil,
                tolerance: nil,
                unit: nil
            )]
            self.perfectScore = 0.0
            self.isPerfect = false
            return
        }

        // 밝기 및 기울기
        let brightness = poseMLAnalyzer.calculateBrightness(from: cgImage)
        let tilt = cameraAngleDetector.detectDutchTilt(faceObservation: faceResult?.observation) ?? 0.0

        // 🆕 이미지 크기 (정규화에 필요)
        let imageSize = CGSize(width: cgImage.width, height: cgImage.height)

        // 🆕 전신 영역 - RTMPose 키포인트에서 정확하게 계산 (정규화된 좌표)
        let bodyRect: CGRect? = {
            if let keypoints = poseResult?.keypoints, !keypoints.isEmpty {
                return calculateBodyRectFromKeypoints(keypoints, imageSize: imageSize)
            }
            // RTMPose 키포인트가 없으면 얼굴 기반 추정 (fallback) - 이미 정규화됨
            return poseMLAnalyzer.estimateBodyRect(from: faceResult?.faceRect)
        }()

        // 카메라 앵글
        let cameraAngle = cameraAngleDetector.detectCameraAngle(
            faceRect: faceResult?.faceRect,
            facePitch: faceResult?.pitch,
            faceObservation: faceResult?.observation
        )

        // 구도
        var compositionType: CompositionType? = nil
        if let faceRect = faceResult?.faceRect {
            let subjectPosition = CGPoint(x: faceRect.midX, y: faceRect.midY)
            compositionType = compositionAnalyzer.classifyComposition(subjectPosition: subjectPosition)
        }

        // 시선
        var gaze: GazeResult? = nil
        if let faceObservation = faceResult?.observation {
            gaze = gazeTracker.trackGaze(from: faceObservation)
        }

        // 🆕 Level 2: 깊이 추정 (동적 프레임 스킵)
        var depth: DepthResult? = lastDepthResult  // 캐시된 값 사용
        if frameSkipper.shouldExecute(level: 2, frameCount: frameCount) {
            // 동적 간격으로 새로 계산
            if let faceRect = faceResult?.faceRect {
                depth = depthEstimator.estimateDistance(
                    faceRect: faceRect,
                    imageWidth: cgImage.width,
                    zoomFactor: 1.0  // TODO: 실제 줌 값
                )
                lastDepthResult = depth  // 캐시 업데이트
            }
        }

        // 🆕 현재 이미지 크기 (위에서 이미 계산됨)
        let currentImageSize = imageSize

        // 🆕 여백 계산 (RTMPose 키포인트 기반)
        var currentPadding: ImagePadding? = nil
        if let keypoints = poseResult?.keypoints, keypoints.count >= 17 {
            // 키포인트를 정규화된 좌표로 변환 (0.0 ~ 1.0)
            let normalizedKeypoints = keypoints.map { kp -> (point: CGPoint, confidence: Float) in
                let normalizedPoint = CGPoint(
                    x: kp.point.x / currentImageSize.width,
                    y: kp.point.y / currentImageSize.height
                )
                return (point: normalizedPoint, confidence: kp.confidence)
            }
            // 구조적 키포인트(0-16)로 여백 계산
            currentPadding = calculatePaddingFromKeypoints(keypoints: normalizedKeypoints)
        }

        // 🆕 프레이밍 분석 추가 (최우선)
        let currentFrame = FrameAnalysis(
            faceRect: faceResult?.faceRect,
            bodyRect: bodyRect,
            brightness: brightness,
            tiltAngle: tilt,
            faceYaw: faceResult?.yaw,
            facePitch: faceResult?.pitch,
            cameraAngle: cameraAngle,
            poseKeypoints: poseResult?.keypoints,
            compositionType: compositionType,
            faceObservation: faceResult?.observation,
            gaze: gaze,
            depth: depth,
            aspectRatio: currentAspectRatio,
            imagePadding: currentPadding
        )

        // 🗑️ 비율 불일치 체크는 이제 StagedFeedbackGenerator가 처리 (Phase 3)

        // ============================================
        // 🆕 v1.5 통합 Gate System 평가 (5단계)
        // ============================================

        // Level 3: Grounding DINO로 정밀 BBox 갱신 (동적 프레임 스킵)
        if frameSkipper.shouldExecute(level: 3, frameCount: frameCount) {
            let uiImage = UIImage(cgImage: cgImage)
            if let ciImage = CIImage(image: uiImage) {
                // 🔥 Level 3 전용 백그라운드 큐에서 비동기 실행
                PerformanceOptimizer.shared.level3Queue.async { [weak self] in
                    self?.personDetector.detectPerson(in: ciImage) { bbox in
                        DispatchQueue.main.async {
                            // 🔧 FIX: nil일 때도 업데이트하여 캐시 stale 방지
                            self?.lastGroundingDINOBBox = bbox
                            if bbox == nil {
                                print("⚠️ Grounding DINO: 인물 미감지 - BBox 초기화")
                            }
                        }
                    }
                }
            }
        }

        // 🔧 FIX: 현재 BBox 결정 - 캐시 유효성 검사 추가
        // bodyRect가 있으면 현재 프레임에 인물이 있다는 의미 → 그것 사용
        // bodyRect가 없고 캐시된 BBox도 없으면 → 기본값 (거의 없는 인물)
        let currentBBox: CGRect
        if let body = bodyRect {
            // Vision에서 현재 프레임에 인물 감지됨 → bodyRect 또는 DINO 결과 사용
            currentBBox = lastGroundingDINOBBox ?? body
        } else if lastGroundingDINOBBox != nil {
            // Vision은 인물 못 찾았지만 DINO에서는 찾음 → DINO 결과 사용
            currentBBox = lastGroundingDINOBBox!
        } else {
            // 둘 다 인물 없음 → 작은 기본값 (인물 미검출로 처리됨)
            currentBBox = CGRect(x: 0.45, y: 0.45, width: 0.01, height: 0.01)
        }

        // 🔧 FIX: 압축감은 현재 프레임 값 사용 (캐시 의존 제거)
        // depth가 nil이면 압축감도 nil로 전달 → Gate에서 "분석 중" 표시
        let currentCompressionIndex: CGFloat?
        if let depthResult = depth {
            currentCompressionIndex = CGFloat(depthResult.compressionIndex)
            lastCompressionIndex = currentCompressionIndex  // 캐시도 업데이트
        } else {
            // 🔧 캐시 사용하지 않음 - 현재 프레임에 depth 없으면 nil
            currentCompressionIndex = nil
        }

        // 포즈 비교 (Gate 4용)
        var poseComparison: PoseComparisonResult? = nil
        if let refKeypoints = reference.poseKeypoints,
           let curKeypoints = poseResult?.keypoints,
           refKeypoints.count >= 133 && curKeypoints.count >= 133 {

            poseComparison = poseComparator.comparePoses(
                referenceKeypoints: refKeypoints,
                currentKeypoints: curKeypoints
            )
        }

        // 통합 Gate System 평가
        var stableFeedback: [FeedbackItem] = []

        // 🆕 v6: 키포인트 변환 (tuple → PoseKeypoint)
        let currentPoseKeypoints: [PoseKeypoint]? = poseResult?.keypoints.map { kp in
            PoseKeypoint(location: kp.point, confidence: kp.confidence)
        }
        let referencePoseKeypoints: [PoseKeypoint]? = reference.poseKeypoints?.map { kp in
            PoseKeypoint(location: kp.point, confidence: kp.confidence)
        }

        if let cached = cachedReference {
            // 🆕 35mm 환산 초점거리 계산
            let currentFocalLength = focalLengthEstimator.focalLengthFromZoom(currentZoomFactor)

            let evaluation = gateSystem.evaluate(
                currentBBox: currentBBox,
                referenceBBox: cached.bbox,
                currentImageSize: currentImageSize,
                referenceImageSize: cached.imageSize,
                compressionIndex: currentCompressionIndex,  // 🔧 FIX: 캐시 대신 현재 값 사용
                referenceCompressionIndex: cached.compressionIndex,
                currentAspectRatio: currentAspectRatio,
                referenceAspectRatio: reference.aspectRatio,
                poseComparison: poseComparison,
                isFrontCamera: isFrontCamera,
                currentKeypoints: currentPoseKeypoints,          // 🆕 v6: 현재 키포인트
                referenceKeypoints: referencePoseKeypoints,      // 🆕 v6: 레퍼런스 키포인트
                currentFocalLength: currentFocalLength,          // 🆕 현재 35mm 환산 초점거리
                referenceFocalLength: referenceFocalLength       // 🆕 레퍼런스 35mm 환산 초점거리
            )

            // v1.5 결과 저장
            self.gateEvaluation = evaluation
            self.v15Feedback = evaluation.primaryFeedback

            // 🆕 v1.5 통합 피드백 생성 (하나의 동작 → 여러 Gate 해결)
            // 🔧 압축감 기반 스마트 피드백: 줌 정보 + 인물 크기 전달
            let currentFocal = focalLengthEstimator.focalLengthFromZoom(currentZoomFactor)
            let targetZoomValue = referenceFocalLength.map {
                CGFloat($0.focalLength35mm) / CGFloat(FocalLengthEstimator.iPhoneBaseFocalLength)
            }

            self.unifiedFeedback = UnifiedFeedbackGenerator.shared.generateUnifiedFeedback(
                from: evaluation,
                isFrontCamera: isFrontCamera,
                currentZoom: currentZoomFactor,
                targetZoom: targetZoomValue,
                currentSubjectSize: currentBBox.width * currentBBox.height,  // 점유율 (정규화됨)
                targetSubjectSize: cached.bbox.width * cached.bbox.height     // 레퍼런스 점유율
            )

            // Gate System 피드백 생성
            let gateFeedbacks = V15FeedbackGenerator.shared.generateFeedbackItems(from: evaluation)

            // 히스테리시스 적용
            for fb in gateFeedbacks {
                feedbackHistory[fb.category, default: 0] += 1

                if feedbackHistory[fb.category]! >= historyThreshold {
                    stableFeedback.append(fb)
                }
            }

            // 사라진 카테고리 히스토리 초기화
            let currentCategories = Set(gateFeedbacks.map { $0.category })
            for (category, _) in feedbackHistory {
                if !currentCategories.contains(category) {
                    feedbackHistory[category] = 0
                }
            }

            print("🎯 v1.5 Gate: \(evaluation.passedCount)/5 통과, 점수: \(String(format: "%.0f%%", Double(evaluation.overallScore) * 100))")
        }

        // ============================================

        // 완벽 상태 감지 (Gate System 기준)
        let isCurrentlyPerfect = gateEvaluation?.allPassed ?? false
        let score = gateEvaluation.map { Double($0.overallScore) } ?? 0.0

        if isCurrentlyPerfect {
            perfectFrameCount += 1
        } else {
            perfectFrameCount = 0
        }

        // 🆕 완료된 피드백 감지 (히스테리시스 적용)
        let currentFeedbackIds = Set(stableFeedback.map { $0.id })
        let disappeared = previousFeedbackIds.subtracting(currentFeedbackIds)

        // 사라진 피드백의 연속 횟수 추적
        for disappearedId in disappeared {
            disappearedFeedbackHistory[disappearedId, default: 0] += 1

            // 5번 연속 사라지면 완료로 판단
            if disappearedFeedbackHistory[disappearedId]! >= disappearedThreshold {
                if let completedItem = instantFeedback.first(where: { $0.id == disappearedId }) {
                    let completed = CompletedFeedback(item: completedItem, completedAt: Date())
                    completedFeedbacks.append(completed)
                }
                // 완료 처리 후 히스토리 초기화
                disappearedFeedbackHistory[disappearedId] = 0
            }
        }

        // 다시 나타난 피드백은 히스토리 초기화
        for (feedbackId, _) in disappearedFeedbackHistory {
            if currentFeedbackIds.contains(feedbackId) {
                disappearedFeedbackHistory[feedbackId] = 0
            }
        }

        // 2초 지난 완료 피드백 제거
        completedFeedbacks.removeAll { !$0.shouldDisplay }

        // 이전 피드백 업데이트
        previousFeedbackIds = currentFeedbackIds

        // 🆕 카테고리별 상태 계산
        let categoryStatuses = calculateCategoryStatuses(from: stableFeedback)

        // 즉시 피드백 업데이트 (메인 쓰레드에서 직접 실행 중이므로 async 불필요)
        self.instantFeedback = stableFeedback
        self.perfectScore = score
        self.isPerfect = perfectFrameCount >= perfectThreshold
        self.categoryStatuses = categoryStatuses
    }

    // MARK: - Category Status Calculation

    /// 카테고리별 상태 계산
    private func calculateCategoryStatuses(from feedbacks: [FeedbackItem]) -> [CategoryStatus] {
        // 모든 카테고리에 대해 상태 생성
        var statusMap: [FeedbackCategory: CategoryStatus] = [:]

        // 각 카테고리 초기화 (모두 만족 상태로 시작)
        for category in FeedbackCategory.allCases {
            statusMap[category] = CategoryStatus(
                category: category,
                isSatisfied: true,
                activeFeedbacks: []
            )
        }

        // 피드백이 있는 카테고리는 불만족 상태로 변경
        for feedback in feedbacks {
            if let category = FeedbackCategory.from(categoryString: feedback.category) {
                var activeFeedbacks = statusMap[category]?.activeFeedbacks ?? []
                activeFeedbacks.append(feedback)

                statusMap[category] = CategoryStatus(
                    category: category,
                    isSatisfied: false,
                    activeFeedbacks: activeFeedbacks.sorted { $0.priority < $1.priority }
                )
            }
        }

        // 우선순위 순서로 정렬하여 반환
        return Array(statusMap.values).sorted { $0.priority < $1.priority }
    }

    // 🗑️ 구식 함수들 제거됨 (새 컴포넌트로 대체)
    // - calculatePerfectScore() → GapAnalyzer.calculateCompletionScore() 사용
    // - calculateBrightness() → VisionAnalyzer.calculateBrightness() 사용
    // - calculateTilt() → CameraAngleDetector.detectDutchTilt() 사용
    // - estimateBodyRect() → VisionAnalyzer.estimateBodyRect() 사용
    // - extractPoseKeypoints() → VisionAnalyzer 내부 사용
    // - estimateCameraAngle() → CameraAngleDetector 사용
    // - comparePoseKeypoints() → AdaptivePoseComparator 사용
    // - calculateAngle() → AdaptivePoseComparator 내부 사용

    // MARK: - 디버그 헬퍼
    private func saveDebugImage(_ image: UIImage, reason: String) {
        guard let data = image.jpegData(compressionQuality: 0.8) else { return }

        let timestamp = DateFormatter.localizedString(from: Date(), dateStyle: .none, timeStyle: .medium)
            .replacingOccurrences(of: ":", with: "-")
        let filename = "debug_\(reason)_\(timestamp).jpg"

        if let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            let fileURL = documentsPath.appendingPathComponent(filename)
            try? data.write(to: fileURL)
            print("🔍 디버그 이미지 저장: \(fileURL.path)")
        }
    }
}