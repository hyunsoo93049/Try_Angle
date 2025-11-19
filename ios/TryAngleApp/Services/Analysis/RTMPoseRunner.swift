import Foundation
import UIKit
import CoreGraphics
import Accelerate

// ONNX Runtime C API (브리징 헤더를 통해 import)
// #import <onnxruntime_c_api.h>
// #import <coreml_provider_factory.h>

// MARK: - RTMPose 결과 구조체
struct RTMPoseResult {
    let keypoints: [(point: CGPoint, confidence: Float)]  // 133개 키포인트
    let boundingBox: CGRect?  // 인물 검출 박스
}

// MARK: - RTMPose Runner (ONNX Runtime)
class RTMPoseRunner {

    private var detectorSession: OpaquePointer?
    private var poseSession: OpaquePointer?
    private var env: OpaquePointer?
    private var memoryInfo: OpaquePointer?

    // ONNX API 포인터 (브리징 헤더를 통해 접근)
    private var api: UnsafePointer<OrtApi>!

    // 모델 경로
    private let detectorModelPath: String
    private let poseModelPath: String

    // 모델 입력 크기
    private let detectorInputSize = CGSize(width: 640, height: 640)
    private let poseInputSize = CGSize(width: 192, height: 256)

    init() {
        // 양자화된 모델 사용
        guard let detectorURL = Bundle.main.url(forResource: "yolox_int8", withExtension: "onnx", subdirectory: "Models/ONNX"),
              let poseURL = Bundle.main.url(forResource: "rtmpose_int8", withExtension: "onnx", subdirectory: "Models/ONNX") else {
            fatalError("ONNX 모델을 찾을 수 없습니다")
        }

        detectorModelPath = detectorURL.path
        poseModelPath = poseURL.path

        setupONNXRuntime()
    }

    deinit {
        cleanup()
    }

    // MARK: - ONNX Runtime 초기화
    private func setupONNXRuntime() {
        // ONNX Runtime API 가져오기
        api = OrtGetApiBase().pointee.GetApi(UInt32(ORT_API_VERSION))

        // 1. Environment 생성
        var status = api.pointee.CreateEnv(ORT_LOGGING_LEVEL_WARNING, "RTMPose", &env)
        guard status == nil, env != nil else {
            print("❌ ONNX Runtime 환경 생성 실패")
            return
        }

        // 2. Memory Info 생성 (CPU 메모리)
        status = api.pointee.CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &memoryInfo)
        guard status == nil, memoryInfo != nil else {
            print("❌ Memory Info 생성 실패")
            return
        }

        // 3. Session Options 설정
        var sessionOptions: OpaquePointer?
        status = api.pointee.CreateSessionOptions(&sessionOptions)
        guard status == nil else {
            print("❌ Session options 생성 실패")
            return
        }

        // 그래프 최적화 활성화
        _ = api.pointee.SetSessionGraphOptimizationLevel(sessionOptions, GraphOptimizationLevel(rawValue: UInt32(ORT_ENABLE_ALL.rawValue)))

        // 🔥 CoreML Execution Provider 활성화 (Apple Neural Engine 사용)
        if OrtSessionOptionsAppendExecutionProvider_CoreML(sessionOptions, UInt32(0)) == nil {
            // CoreML EP 활성화 성공 (nil = no error)
            print("✅ CoreML Execution Provider 활성화 (ANE 가속)")
        }

        // 병렬 처리 설정
        _ = api.pointee.SetIntraOpNumThreads(sessionOptions, 4)
        _ = api.pointee.SetInterOpNumThreads(sessionOptions, 2)

        // 4. 세션 생성
        // Detector 세션
        status = api.pointee.CreateSession(env, detectorModelPath, sessionOptions, &detectorSession)
        if status != nil || detectorSession == nil {
            print("❌ Detector 세션 생성 실패")
        } else {
            print("✅ YOLOX Detector 로드 성공")
        }

        // Pose 세션
        status = api.pointee.CreateSession(env, poseModelPath, sessionOptions, &poseSession)
        if status != nil || poseSession == nil {
            print("❌ Pose 세션 생성 실패")
        } else {
            print("✅ RTMPose 로드 성공")
        }

        // Session options 해제
        if let opts = sessionOptions {
            api.pointee.ReleaseSessionOptions(opts)
        }
    }

    // MARK: - 정리
    private func cleanup() {
        if let session = detectorSession {
            api.pointee.ReleaseSession(session)
        }
        if let session = poseSession {
            api.pointee.ReleaseSession(session)
        }
        if let info = memoryInfo {
            api.pointee.ReleaseMemoryInfo(info)
        }
        if let e = env {
            api.pointee.ReleaseEnv(e)
        }
    }

    // MARK: - 포즈 추정
    func detectPose(from image: UIImage) -> RTMPoseResult? {
        guard let detectorSession = detectorSession,
              let poseSession = poseSession else {
            print("❌ ONNX 세션이 초기화되지 않음")
            return nil
        }

        // 1. YOLOX로 인물 검출
        guard let personBox = detectPerson(from: image, session: detectorSession) else {
            return nil
        }

        // 2. 검출된 영역 크롭 및 RTMPose 입력 준비
        guard let croppedImage = cropImage(image, to: personBox),
              let poseInput = preprocessImageForPose(croppedImage) else {
            return nil
        }

        // 3. RTMPose로 키포인트 추정
        guard let keypoints = runPoseEstimation(input: poseInput, session: poseSession) else {
            return nil
        }

        // 4. 키포인트를 원본 이미지 좌표계로 변환
        let transformedKeypoints = transformKeypoints(keypoints, from: personBox, imageSize: image.size)

        return RTMPoseResult(keypoints: transformedKeypoints, boundingBox: personBox)
    }

    // MARK: - YOLOX 인물 검출
    private func detectPerson(from image: UIImage, session: OpaquePointer) -> CGRect? {
        guard let inputData = preprocessImageForDetector(image) else {
            return nil
        }

        // YOLOX 입력: [1, 3, 640, 640]
        let inputShape: [Int64] = [1, 3, 640, 640]
        var inputTensor: OpaquePointer?

        // 입력 텐서 생성
        let status = inputData.withUnsafeBytes { (rawPtr: UnsafeRawBufferPointer) -> OrtStatusPtr? in
            let floatPtr = rawPtr.bindMemory(to: Float.self)
            let mutablePtr = UnsafeMutableRawPointer(mutating: floatPtr.baseAddress!)

            return api.pointee.CreateTensorWithDataAsOrtValue(
                memoryInfo,
                mutablePtr,
                inputData.count * MemoryLayout<Float>.size,
                inputShape,
                4,
                ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,
                &inputTensor
            )
        }

        guard status == nil, inputTensor != nil else {
            print("❌ YOLOX 입력 텐서 생성 실패")
            return nil
        }
        defer { if let tensor = inputTensor { api.pointee.ReleaseValue(tensor) } }

        // 추론 실행
        var outputTensor: OpaquePointer?

        let runStatus = "images".withCString { inputNamePtr in
            "output0".withCString { outputNamePtr in
                var inputNames: [UnsafePointer<CChar>?] = [inputNamePtr]
                var outputNames: [UnsafePointer<CChar>?] = [outputNamePtr]

                return api.pointee.Run(
                    session,
                    nil,
                    &inputNames,
                    &inputTensor,
                    1,
                    &outputNames,
                    1,
                    &outputTensor
                )
            }
        }

        guard runStatus == nil, outputTensor != nil else {
            print("❌ YOLOX 추론 실패")
            return nil
        }
        defer { if let tensor = outputTensor { api.pointee.ReleaseValue(tensor) } }

        // 출력 파싱 (가장 높은 신뢰도의 person bbox 찾기)
        return parseBoundingBox(from: outputTensor!)
    }

    // MARK: - Bounding Box 파싱
    private func parseBoundingBox(from tensor: OpaquePointer) -> CGRect? {
        var outputData: UnsafeMutableRawPointer?
        let status = api.pointee.GetTensorMutableData(tensor, &outputData)
        guard status == nil, let data = outputData else {
            return nil
        }

        let floatPtr = data.bindMemory(to: Float.self, capacity: 8400 * 85)

        var bestBox: (x: Float, y: Float, w: Float, h: Float, score: Float)?

        // YOLOX 출력: [1, 8400, 85] (cx, cy, w, h, obj_conf, class_scores...)
        for i in 0..<8400 {
            let offset = i * 85
            let objConf = floatPtr[offset + 4]
            let personScore = floatPtr[offset + 5] * objConf  // class 0 = person

            if personScore > 0.5 {
                let cx = floatPtr[offset + 0]
                let cy = floatPtr[offset + 1]
                let w = floatPtr[offset + 2]
                let h = floatPtr[offset + 3]

                if bestBox == nil || personScore > bestBox!.score {
                    bestBox = (cx, cy, w, h, personScore)
                }
            }
        }

        guard let box = bestBox else {
            return nil
        }

        // YOLOX 좌표를 normalized 좌표로 변환 (0~1)
        let scale: Float = 640.0
        return CGRect(
            x: CGFloat((box.x - box.w / 2) / scale),
            y: CGFloat((box.y - box.h / 2) / scale),
            width: CGFloat(box.w / scale),
            height: CGFloat(box.h / scale)
        )
    }

    // MARK: - RTMPose 추론
    private func runPoseEstimation(input: [Float], session: OpaquePointer) -> [(point: CGPoint, confidence: Float)]? {
        // RTMPose 입력: [1, 3, 256, 192]
        let inputShape: [Int64] = [1, 3, 256, 192]
        var inputTensor: OpaquePointer?

        let status = input.withUnsafeBytes { (rawPtr: UnsafeRawBufferPointer) -> OrtStatusPtr? in
            let floatPtr = rawPtr.bindMemory(to: Float.self)
            let mutablePtr = UnsafeMutableRawPointer(mutating: floatPtr.baseAddress!)

            return api.pointee.CreateTensorWithDataAsOrtValue(
                memoryInfo,
                mutablePtr,
                input.count * MemoryLayout<Float>.size,
                inputShape,
                4,
                ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,
                &inputTensor
            )
        }

        guard status == nil, inputTensor != nil else {
            print("❌ RTMPose 입력 텐서 생성 실패")
            return nil
        }
        defer { if let tensor = inputTensor { api.pointee.ReleaseValue(tensor) } }

        // 추론 실행
        var outputTensor: OpaquePointer?

        let runStatus = "input".withCString { inputNamePtr in
            "output".withCString { outputNamePtr in
                var inputNames: [UnsafePointer<CChar>?] = [inputNamePtr]
                var outputNames: [UnsafePointer<CChar>?] = [outputNamePtr]

                return api.pointee.Run(
                    session,
                    nil,
                    &inputNames,
                    &inputTensor,
                    1,
                    &outputNames,
                    1,
                    &outputTensor
                )
            }
        }

        guard runStatus == nil, outputTensor != nil else {
            print("❌ RTMPose 추론 실패")
            return nil
        }
        defer { if let tensor = outputTensor { api.pointee.ReleaseValue(tensor) } }

        // 키포인트 파싱
        return parseKeypoints(from: outputTensor!)
    }

    // MARK: - 키포인트 파싱
    private func parseKeypoints(from tensor: OpaquePointer) -> [(point: CGPoint, confidence: Float)]? {
        var outputData: UnsafeMutableRawPointer?
        let status = api.pointee.GetTensorMutableData(tensor, &outputData)
        guard status == nil, let data = outputData else {
            return nil
        }

        // RTMPose 출력: [1, 133, 3] (x, y, confidence)
        let floatPtr = data.bindMemory(to: Float.self, capacity: 133 * 3)

        var keypoints: [(point: CGPoint, confidence: Float)] = []
        for i in 0..<133 {
            let offset = i * 3
            let x = CGFloat(floatPtr[offset + 0]) / 192.0  // normalize to 0~1
            let y = CGFloat(floatPtr[offset + 1]) / 256.0  // normalize to 0~1
            let conf = floatPtr[offset + 2]

            keypoints.append((CGPoint(x: x, y: y), conf))
        }

        return keypoints
    }

    // MARK: - 키포인트 좌표 변환 (crop -> 원본 이미지)
    private func transformKeypoints(
        _ keypoints: [(point: CGPoint, confidence: Float)],
        from cropBox: CGRect,
        imageSize: CGSize
    ) -> [(point: CGPoint, confidence: Float)] {
        return keypoints.map { kp in
            let x = cropBox.minX + kp.point.x * cropBox.width
            let y = cropBox.minY + kp.point.y * cropBox.height
            return (CGPoint(x: x * imageSize.width, y: y * imageSize.height), kp.confidence)
        }
    }

    // MARK: - 이미지 크롭
    private func cropImage(_ image: UIImage, to rect: CGRect) -> UIImage? {
        guard let cgImage = image.cgImage else { return nil }

        let imageWidth = CGFloat(cgImage.width)
        let imageHeight = CGFloat(cgImage.height)

        let cropRect = CGRect(
            x: rect.minX * imageWidth,
            y: rect.minY * imageHeight,
            width: rect.width * imageWidth,
            height: rect.height * imageHeight
        )

        guard let croppedCGImage = cgImage.cropping(to: cropRect) else {
            return nil
        }

        return UIImage(cgImage: croppedCGImage)
    }

    // MARK: - YOLOX 전처리
    private func preprocessImageForDetector(_ image: UIImage) -> [Float]? {
        return preprocessImage(image, targetSize: detectorInputSize)
    }

    // MARK: - RTMPose 전처리
    private func preprocessImageForPose(_ image: UIImage) -> [Float]? {
        return preprocessImage(image, targetSize: poseInputSize)
    }

    // MARK: - 이미지 전처리 (공통)
    private func preprocessImage(_ image: UIImage, targetSize: CGSize) -> [Float]? {
        guard let cgImage = image.cgImage else { return nil }

        let width = Int(targetSize.width)
        let height = Int(targetSize.height)

        // RGB 컨텍스트 생성
        guard let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
        ) else { return nil }

        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))

        guard let pixelData = context.data else { return nil }
        let buffer = pixelData.bindMemory(to: UInt8.self, capacity: width * height * 4)

        // CHW 형식으로 변환 및 정규화 (ImageNet mean/std)
        var floatArray = [Float](repeating: 0, count: 3 * width * height)

        let mean: [Float] = [0.485, 0.456, 0.406]
        let std: [Float] = [0.229, 0.224, 0.225]

        for y in 0..<height {
            for x in 0..<width {
                let pixelIndex = (y * width + x) * 4
                let r = Float(buffer[pixelIndex + 0]) / 255.0
                let g = Float(buffer[pixelIndex + 1]) / 255.0
                let b = Float(buffer[pixelIndex + 2]) / 255.0

                // CHW layout: [C, H, W]
                floatArray[0 * (width * height) + y * width + x] = (r - mean[0]) / std[0]
                floatArray[1 * (width * height) + y * width + x] = (g - mean[1]) / std[1]
                floatArray[2 * (width * height) + y * width + x] = (b - mean[2]) / std[2]
            }
        }

        return floatArray
    }
}
