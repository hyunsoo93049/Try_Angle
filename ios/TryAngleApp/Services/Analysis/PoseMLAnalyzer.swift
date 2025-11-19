import Foundation
import Vision
import UIKit

// MARK: - PoseML 분석기 (RTMPose via ONNX Runtime)
class PoseMLAnalyzer {

    // RTMPose Runner (ONNX Runtime)
    private let rtmPoseRunner: RTMPoseRunner?

    // Vision은 얼굴 감지용으로 계속 사용
    private lazy var faceDetectionRequest: VNDetectFaceLandmarksRequest = {
        let request = VNDetectFaceLandmarksRequest()
        request.revision = VNDetectFaceLandmarksRequestRevision3
        return request
    }()

    // 🐛 디버그 로그 파일 경로
    private lazy var logFileURL: URL? = {
        if let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            return documentsPath.appendingPathComponent("pose_debug.txt")
        }
        return nil
    }()

    init() {
        print("🚀 PoseMLAnalyzer init() 시작")

        // RTMPose Runner 초기화 시도 (stored property 먼저 초기화)
        rtmPoseRunner = RTMPoseRunner()

        // 초기화 완료 후 로그
        logToFile("🚀 PoseMLAnalyzer init() 시작 - \(Date())")

        if rtmPoseRunner != nil {
            print("✅ RTMPose Runner 초기화 성공")
            logToFile("✅ RTMPose 사용 (ONNX Runtime with CoreML EP)")
        } else {
            print("❌ RTMPose Runner 초기화 실패 - ONNX 모델을 찾을 수 없음")
            logToFile("❌ RTMPose 초기화 실패")
        }

        print("🚀 PoseMLAnalyzer init() 완료")
    }

    // 🐛 파일에 로그 기록
    private func logToFile(_ message: String) {
        guard let logFileURL = logFileURL else { return }

        let timestamp = DateFormatter.localizedString(from: Date(), dateStyle: .none, timeStyle: .medium)
        let logMessage = "[\(timestamp)] \(message)\n"

        if let data = logMessage.data(using: .utf8) {
            if FileManager.default.fileExists(atPath: logFileURL.path) {
                if let fileHandle = try? FileHandle(forWritingTo: logFileURL) {
                    fileHandle.seekToEndOfFile()
                    fileHandle.write(data)
                    fileHandle.closeFile()
                }
            } else {
                try? data.write(to: logFileURL)
            }
        }

        // 콘솔에도 출력
        print(message)
    }

    // MARK: - 얼굴 + 포즈 동시 분석 (VisionAnalyzer와 동일한 인터페이스)
    private var analysisCallCount = 0
    func analyzeFaceAndPose(from image: UIImage) -> (face: FaceAnalysisResult?, pose: PoseAnalysisResult?) {
        analysisCallCount += 1

        // 10번마다 로그 (너무 많은 로그 방지)
        if analysisCallCount % 10 == 1 {
            logToFile("🔍 analyzeFaceAndPose() 호출됨 (호출 횟수: \(analysisCallCount))")
        }

        // 얼굴 감지 (Vision 계속 사용 - 가장 정확함)
        let faceResult = detectFace(from: image)

        // RTMPose 포즈 감지 (ONNX Runtime)
        let poseResult = detectPoseWithRTMPose(from: image)

        // 10번마다 상세 로그
        if analysisCallCount % 10 == 1 {
            logToFile("   얼굴: \(faceResult != nil ? "✓" : "✗") | 포즈: \(poseResult != nil ? "✓ (RTMPose)" : "✗")")
        }

        return (faceResult, poseResult)
    }

    // MARK: - 얼굴 감지 (Vision)
    private func detectFace(from image: UIImage) -> FaceAnalysisResult? {
        guard let cgImage = image.cgImage else { return nil }

        let handler = VNImageRequestHandler(
            cgImage: cgImage,
            orientation: image.cgImageOrientation,
            options: [:]
        )
        try? handler.perform([faceDetectionRequest])

        guard let observation = faceDetectionRequest.results?.first else {
            return nil
        }

        return FaceAnalysisResult(
            faceRect: observation.boundingBox,
            landmarks: observation.landmarks,
            yaw: observation.yaw?.floatValue,
            pitch: observation.pitch?.floatValue,
            roll: observation.roll?.floatValue,
            observation: observation
        )
    }

    // MARK: - RTMPose 포즈 감지
    private func detectPoseWithRTMPose(from image: UIImage) -> PoseAnalysisResult? {
        guard let runner = rtmPoseRunner else {
            return nil
        }

        guard let rtmResult = runner.detectPose(from: image) else {
            return nil
        }

        // RTMPose 키포인트를 PoseAnalysisResult 형식으로 변환
        // RTMPose는 133개 키포인트 제공 (전신 + 얼굴 + 손 + 발)
        // 기존 PoseAnalysisResult 형식으로 변환 (17개 주요 키포인트)

        // COCO 17 keypoints 매핑
        // 0: nose, 1-2: eyes, 3-4: ears, 5-6: shoulders, 7-8: elbows,
        // 9-10: wrists, 11-12: hips, 13-14: knees, 15-16: ankles

        // RTMPose 133 키포인트 중 COCO 호환 인덱스 추출
        let cocoIndices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        var keypoints: [(point: CGPoint, confidence: Float)] = []

        for idx in cocoIndices {
            if idx < rtmResult.keypoints.count {
                let kp = rtmResult.keypoints[idx]
                keypoints.append((point: kp.point, confidence: kp.confidence))
            } else {
                keypoints.append((point: CGPoint.zero, confidence: 0.0))
            }
        }

        return PoseAnalysisResult(keypoints: keypoints)
    }

    /// 밝기 계산 (VisionAnalyzer와 호환)
    func calculateBrightness(from cgImage: CGImage) -> Float {
        let width = min(cgImage.width, 100)
        let height = min(cgImage.height, 100)

        guard let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return 0.5 }

        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        guard let data = context.data else { return 0.5 }

        let buffer = data.bindMemory(to: UInt8.self, capacity: width * height * 4)
        var totalBrightness: Float = 0

        for i in stride(from: 0, to: width * height * 4, by: 4) {
            let r = Float(buffer[i]) / 255.0
            let g = Float(buffer[i + 1]) / 255.0
            let b = Float(buffer[i + 2]) / 255.0
            totalBrightness += (r + g + b) / 3.0
        }

        return totalBrightness / Float(width * height)
    }

    /// 전신 영역 추정 (VisionAnalyzer와 호환)
    func estimateBodyRect(from faceRect: CGRect?) -> CGRect? {
        guard let face = faceRect else { return nil }

        let bodyWidth = face.width * 3
        let bodyHeight = face.height * 7
        let bodyX = face.midX - bodyWidth / 2
        let bodyY = face.minY

        return CGRect(x: bodyX, y: bodyY, width: bodyWidth, height: bodyHeight)
    }
}
