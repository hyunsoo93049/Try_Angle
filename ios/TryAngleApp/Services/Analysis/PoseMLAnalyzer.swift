import Foundation
import Vision
import UIKit
import CoreML
// TensorFlowLite wrapper is in TensorFlowLiteWrapper.swift

// MARK: - PoseML 분석기 (YOLO11s-pose + MoveNet Lightning)
class PoseMLAnalyzer {

    // YOLO11s-pose CoreML 모델
    private var yoloModel: MLModel?

    // MoveNet Lightning TFLite
    private var moveNetInterpreter: Interpreter?

    // Vision은 얼굴 감지용으로만 계속 사용
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
        logToFile("🚀 PoseMLAnalyzer init() 시작 - \(Date())")
        loadModels()
        print("🚀 PoseMLAnalyzer init() 완료")
        logToFile("🚀 PoseMLAnalyzer init() 완료")
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

    private func loadModels() {
        logToFile("📦 모델 로딩 시작")

        // YOLO11s-pose 모델 로드
        do {
            guard let modelURL = Bundle.main.url(forResource: "yolo11s-pose", withExtension: "mlpackage") else {
                logToFile("❌ YOLO 모델 파일을 찾을 수 없음 (yolo11s-pose.mlpackage)")
                return
            }
            logToFile("📂 YOLO 모델 파일 찾음: \(modelURL.path)")
            let config = MLModelConfiguration()
            config.computeUnits = .all  // CPU + GPU + Neural Engine
            yoloModel = try MLModel(contentsOf: modelURL, configuration: config)
            logToFile("✅ YOLO11s-pose 모델 로드 완료")
        } catch {
            logToFile("❌ YOLO 모델 로드 실패: \(error)")
        }

        // MoveNet TFLite 모델 로드
        do {
            guard let modelPath = Bundle.main.path(forResource: "movenet_lightning", ofType: "tflite") else {
                logToFile("❌ MoveNet 모델 파일을 찾을 수 없음 (movenet_lightning.tflite)")
                logToFile("⚠️ YOLO만 사용하여 계속 진행합니다")
                return
            }
            logToFile("📂 MoveNet 모델 파일 찾음: \(modelPath)")
            var options = Interpreter.Options()
            options.threadCount = 4
            moveNetInterpreter = try Interpreter(modelPath: modelPath, options: options)
            try moveNetInterpreter?.allocateTensors()
            logToFile("✅ MoveNet Lightning 모델 로드 완료")
        } catch {
            logToFile("❌ MoveNet 모델 로드 실패: \(error)")
            logToFile("⚠️ YOLO만 사용하여 계속 진행합니다")
        }

        logToFile("📦 모델 로딩 완료 - YOLO: \(yoloModel != nil), MoveNet: \(moveNetInterpreter != nil)")
    }

    // MARK: - 얼굴 + 포즈 동시 분석 (VisionAnalyzer와 동일한 인터페이스)
    private var analysisCallCount = 0
    func analyzeFaceAndPose(from image: UIImage) -> (face: FaceAnalysisResult?, pose: PoseAnalysisResult?) {
        analysisCallCount += 1

        // 10번마다 로그 (너무 많은 로그 방지)
        if analysisCallCount % 10 == 1 {
            logToFile("🔍 analyzeFaceAndPose() 호출됨 (호출 횟수: \(analysisCallCount))")
        }

        guard let cgImage = image.cgImage else {
            logToFile("❌ cgImage 없음")
            return (nil, nil)
        }

        // 얼굴 감지 (Vision 계속 사용 - 가장 정확함)
        let faceResult = detectFace(from: image)

        // 포즈 감지 (YOLO + MoveNet 융합)
        let yoloPose = detectPoseWithYOLO(from: cgImage)
        let moveNetPose = detectPoseWithMoveNet(from: cgImage)

        // YOLO와 MoveNet 결과 융합 (둘 다 있으면 융합, 하나만 있으면 그것 사용)
        let fusedPose = fusePoseResults(yolo: yoloPose, moveNet: moveNetPose)

        // 10번마다 상세 로그
        if analysisCallCount % 10 == 1 {
            logToFile("   얼굴: \(faceResult != nil ? "✓" : "✗") | YOLO: \(yoloPose != nil ? "\(yoloPose!.keypoints.count)개" : "✗") | MoveNet: \(moveNetPose != nil ? "\(moveNetPose!.keypoints.count)개" : "✗") | 융합: \(fusedPose != nil ? "\(fusedPose!.keypoints.count)개" : "✗")")
        }

        return (faceResult, fusedPose)
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

    // MARK: - 포즈 감지 (YOLO11s-pose)
    private func detectPoseWithYOLO(from cgImage: CGImage) -> PoseAnalysisResult? {
        guard let model = yoloModel else {
            print("⚠️ YOLO 모델이 로드되지 않음")
            return nil
        }

        // YOLO 입력: 1280x1280 이미지 (고해상도로 작은 관절도 검출)
        let inputSize = CGSize(width: 1280, height: 1280)
        guard let resizedImage = resize(cgImage: cgImage, to: inputSize) else {
            return nil
        }

        guard let pixelBuffer = cgImageToPixelBuffer(resizedImage, size: inputSize) else {
            return nil
        }

        do {
            // YOLO 추론
            let input = try MLDictionaryFeatureProvider(dictionary: ["image": pixelBuffer])
            let output = try model.prediction(from: input)

            // YOLO 출력: (1, 56, 8400) 형태
            // 56 = 17 keypoints * 3 (x, y, confidence) + 5 (bbox + objectness)
            guard let outputArray = output.featureValue(for: "output")?.multiArrayValue else {
                return nil
            }

            // 키포인트 파싱
            let keypoints = parseYOLOKeypoints(from: outputArray, originalSize: CGSize(width: cgImage.width, height: cgImage.height))

            return PoseAnalysisResult(
                keypoints: keypoints
            )
        } catch {
            print("❌ YOLO 추론 실패: \(error)")
            return nil
        }
    }

    // MARK: - MoveNet 포즈 감지
    private func detectPoseWithMoveNet(from cgImage: CGImage) -> PoseAnalysisResult? {
        guard let interpreter = moveNetInterpreter else {
            logToFile("⚠️ MoveNet interpreter 없음 - 초기화 실패했을 가능성")
            return nil
        }

        // MoveNet 입력: 192x192 이미지
        let inputSize = CGSize(width: 192, height: 192)
        guard let resizedImage = resize(cgImage: cgImage, to: inputSize) else {
            logToFile("❌ MoveNet: 이미지 리사이즈 실패")
            return nil
        }

        guard let inputData = preprocessForMoveNet(resizedImage) else {
            logToFile("❌ MoveNet: 전처리 실패")
            return nil
        }

        do {
            try interpreter.copy(inputData, toInputAt: 0)
            try interpreter.invoke()

            // MoveNet 출력: (1, 1, 17, 3) - [y, x, confidence]
            let outputTensor = try interpreter.output(at: 0)
            let keypoints = parseMoveNetKeypoints(from: outputTensor.data,
                                                  originalSize: CGSize(width: cgImage.width, height: cgImage.height))

            return PoseAnalysisResult(keypoints: keypoints)
        } catch let error as InterpreterError {
            logToFile("❌ MoveNet 추론 실패 (Interpreter): \(error.localizedDescription)")
            return nil
        } catch {
            logToFile("❌ MoveNet 추론 실패 (Unknown): \(error)")
            return nil
        }
    }

    // MARK: - YOLO 키포인트 파싱
    private func parseYOLOKeypoints(from output: MLMultiArray, originalSize: CGSize) -> [(point: CGPoint, confidence: Float)] {
        // YOLO pose 출력 형식: (1, 56, 8400)
        // 56 = bbox(4) + objectness(1) + 17 keypoints * 3 (x, y, conf)

        var keypoints: [(point: CGPoint, confidence: Float)] = []

        // 가장 높은 objectness를 가진 detection 찾기
        var maxObjectness: Float = 0
        var maxIndex = 0

        let detectionCount = output.shape[2].intValue
        for i in 0..<detectionCount {
            let objectness = output[[0, 4, i] as [NSNumber]].floatValue
            if objectness > maxObjectness {
                maxObjectness = objectness
                maxIndex = i
            }
        }

        // 🔥 Objectness threshold: 너무 낮으면 무시 (완화: 0.2)
        if maxObjectness < 0.2 {
            logToFile("⚠️ YOLO objectness 너무 낮음: \(maxObjectness) < 0.2 - 포즈 무시")
            return []
        }

        logToFile("✅ YOLO detection - objectness: \(maxObjectness)")

        // 해당 detection의 17개 keypoints 추출
        for kpIdx in 0..<17 {
            let baseIdx = 5 + kpIdx * 3
            let x = output[[0, baseIdx, maxIndex] as [NSNumber]].floatValue / 1280.0
            let y = output[[0, baseIdx + 1, maxIndex] as [NSNumber]].floatValue / 1280.0
            let conf = output[[0, baseIdx + 2, maxIndex] as [NSNumber]].floatValue

            keypoints.append((
                point: CGPoint(x: CGFloat(x), y: CGFloat(y)),
                confidence: conf
            ))
        }

        // 🔥 신뢰도 높은 키포인트 개수 세기
        let visibleCount = keypoints.filter { $0.confidence >= 0.5 }.count
        logToFile("   YOLO keypoints: 전체 \(keypoints.count)개, 신뢰도 ≥ 0.5: \(visibleCount)개")

        return keypoints
    }

    // MARK: - MoveNet 키포인트 파싱
    private func parseMoveNetKeypoints(from data: Data, originalSize: CGSize) -> [(point: CGPoint, confidence: Float)] {
        var keypoints: [(point: CGPoint, confidence: Float)] = []

        let floatArray = data.withUnsafeBytes { (ptr: UnsafeRawBufferPointer) -> [Float] in
            Array(ptr.bindMemory(to: Float.self))
        }

        // MoveNet 출력: [y, x, confidence] * 17
        for i in 0..<17 {
            let baseIdx = i * 3
            let y = CGFloat(floatArray[baseIdx])
            let x = CGFloat(floatArray[baseIdx + 1])
            let conf = floatArray[baseIdx + 2]

            keypoints.append((point: CGPoint(x: x, y: y), confidence: conf))
        }

        // 🔥 신뢰도 높은 키포인트 개수 세기
        let visibleCount = keypoints.filter { $0.confidence >= 0.5 }.count
        logToFile("✅ MoveNet keypoints: 전체 \(keypoints.count)개, 신뢰도 ≥ 0.5: \(visibleCount)개")

        return keypoints
    }

    // MARK: - Helper Functions

    private func resize(cgImage: CGImage, to size: CGSize) -> CGImage? {
        let context = CGContext(
            data: nil,
            width: Int(size.width),
            height: Int(size.height),
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
        )
        context?.draw(cgImage, in: CGRect(origin: .zero, size: size))
        return context?.makeImage()
    }

    private func cgImageToPixelBuffer(_ cgImage: CGImage, size: CGSize) -> CVPixelBuffer? {
        let attrs = [
            kCVPixelBufferCGImageCompatibilityKey: kCFBooleanTrue,
            kCVPixelBufferCGBitmapContextCompatibilityKey: kCFBooleanTrue
        ] as CFDictionary

        var pixelBuffer: CVPixelBuffer?
        let status = CVPixelBufferCreate(
            kCFAllocatorDefault,
            Int(size.width),
            Int(size.height),
            kCVPixelFormatType_32BGRA,
            attrs,
            &pixelBuffer
        )

        guard status == kCVReturnSuccess, let buffer = pixelBuffer else {
            return nil
        }

        CVPixelBufferLockBaseAddress(buffer, [])
        defer { CVPixelBufferUnlockBaseAddress(buffer, []) }

        let context = CGContext(
            data: CVPixelBufferGetBaseAddress(buffer),
            width: Int(size.width),
            height: Int(size.height),
            bitsPerComponent: 8,
            bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue
        )

        context?.draw(cgImage, in: CGRect(origin: .zero, size: size))

        return buffer
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

    /// MoveNet 전처리 (192x192 RGB → Data)
    private func preprocessForMoveNet(_ cgImage: CGImage) -> Data? {
        let width = 192
        let height = 192

        guard let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 3,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.none.rawValue
        ) else { return nil }

        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        guard let data = context.data else { return nil }

        // RGB 데이터를 Data로 변환 (uint8)
        let pixelData = Data(bytes: data, count: width * height * 3)
        return pixelData
    }

    /// YOLO와 MoveNet 포즈 결과 융합
    private func fusePoseResults(yolo: PoseAnalysisResult?, moveNet: PoseAnalysisResult?) -> PoseAnalysisResult? {
        // 둘 다 없으면 nil
        guard yolo != nil || moveNet != nil else { return nil }

        // 하나만 있으면 그것 반환
        if yolo == nil { return moveNet }
        if moveNet == nil { return yolo }

        // 둘 다 있으면 confidence 기준으로 융합
        guard let yoloKeypoints = yolo?.keypoints,
              let moveNetKeypoints = moveNet?.keypoints else {
            return yolo // fallback
        }

        var fusedKeypoints: [(point: CGPoint, confidence: Float)] = []

        for i in 0..<min(yoloKeypoints.count, moveNetKeypoints.count) {
            let yoloKp = yoloKeypoints[i]
            let moveNetKp = moveNetKeypoints[i]

            // Confidence가 높은 쪽 선택
            if yoloKp.confidence > moveNetKp.confidence {
                fusedKeypoints.append(yoloKp)
            } else {
                fusedKeypoints.append(moveNetKp)
            }
        }

        return PoseAnalysisResult(keypoints: fusedKeypoints)
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

// UIImage extension은 이미 UIImage+Orientation.swift에 정의되어 있음
