// GroundingDINOONNX.swift
// Grounding DINO ONNX Runtime 구현 (최적화 버전)
// 수정일: 2025-12-09

import Foundation
import CoreImage
import UIKit
import onnxruntime_objc
import Accelerate

class GroundingDINOONNX {

    private var ortSession: ORTSession?
    private var ortEnv: ORTEnv?
    private let inputSize = 800  // Grounding DINO 입력 크기

    // 🔥 [수정 1] CIContext를 클래스 멤버로 선언하여 재사용 (성능 최적화 & 발열 감소)
    // useSoftwareRenderer: false로 설정하여 가능한 경우 GPU를 사용하도록 유도
    private let ciContext = CIContext(options: [.useSoftwareRenderer: false])

    // "person" 토큰 (BERT tokenizer)
    // [CLS] person [SEP] = [101, 2711, 102]
    private let personTokenIds: [Int64] = [101, 2711, 102]

    // MARK: - 세션 상태
    private(set) var isSessionLoaded: Bool = false

    // 로딩 완료 콜백
    var onLoadingComplete: ((Bool) -> Void)?

    // MARK: - Initialization
    init(completion: ((Bool) -> Void)? = nil) {
        self.onLoadingComplete = completion

        // 🔥 [수정] 백그라운드에서 모델 로딩 (UI 블로킹 방지)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.setupONNXRuntime()
        }
    }

    private func setupONNXRuntime() {
        do {
            // ONNX Runtime 환경 설정
            ortEnv = try ORTEnv(loggingLevel: .warning)

            // 모델 경로
            guard let modelPath = Bundle.main.path(forResource: "grounding_dino", ofType: "onnx") else {
                print("❌ Grounding DINO ONNX 모델을 찾을 수 없습니다")
                print("   Models/GroundingDINO/grounding_dino.onnx 경로를 확인하세요")
                notifyLoadingComplete(success: false)
                return
            }

            // 1차 시도: CoreML EP (GPU 가속)
            if let session = tryCreateSessionWithCoreML(modelPath: modelPath) {
                ortSession = session
                isSessionLoaded = true
                print("✅ Grounding DINO ONNX 모델 로드 성공 (CoreML GPU)")
                print("   입력 크기: \(inputSize)x\(inputSize)")
                notifyLoadingComplete(success: true)
                return
            }

            // 2차 시도: CPU만 (CoreML 실패 시 폴백)
            print("⚠️ CoreML EP 실패, CPU 모드로 재시도...")
            if let session = tryCreateSessionCPUOnly(modelPath: modelPath) {
                ortSession = session
                isSessionLoaded = true
                print("✅ Grounding DINO ONNX 모델 로드 성공 (CPU)")
                print("   입력 크기: \(inputSize)x\(inputSize)")
                notifyLoadingComplete(success: true)
                return
            }

            // 둘 다 실패
            isSessionLoaded = false
            print("❌ Grounding DINO 모델 로드 완전 실패")
            notifyLoadingComplete(success: false)

        } catch {
            isSessionLoaded = false
            print("❌ ONNX Runtime 설정 실패: \(error)")
            notifyLoadingComplete(success: false)
        }
    }

    // CoreML EP로 세션 생성 시도
    private func tryCreateSessionWithCoreML(modelPath: String) -> ORTSession? {
        do {
            let sessionOptions = try ORTSessionOptions()
            try sessionOptions.setGraphOptimizationLevel(.all)
            try sessionOptions.setIntraOpNumThreads(4)

            // CoreML EP 추가
            try sessionOptions.appendCoreMLExecutionProvider(with: .init())

            let session = try ORTSession(env: ortEnv!, modelPath: modelPath, sessionOptions: sessionOptions)
            print("✅ GroundingDINO: CoreML(GPU) 가속 활성화 성공")
            return session
        } catch {
            print("⚠️ CoreML EP 세션 생성 실패: \(error.localizedDescription)")
            return nil
        }
    }

    // CPU만으로 세션 생성
    private func tryCreateSessionCPUOnly(modelPath: String) -> ORTSession? {
        do {
            let sessionOptions = try ORTSessionOptions()
            try sessionOptions.setGraphOptimizationLevel(.all)
            try sessionOptions.setIntraOpNumThreads(4)
            // CoreML EP 없이 CPU만 사용

            let session = try ORTSession(env: ortEnv!, modelPath: modelPath, sessionOptions: sessionOptions)
            return session
        } catch {
            print("❌ CPU 세션 생성도 실패: \(error.localizedDescription)")
            return nil
        }
    }

    // 콜백 호출 헬퍼
    private func notifyLoadingComplete(success: Bool) {
        DispatchQueue.main.async { [weak self] in
            self?.onLoadingComplete?(success)
        }
    }

    // MARK: - Person Detection
    func detectPerson(in image: CIImage, completion: @escaping (CGRect?) -> Void) {
        guard let session = ortSession else {
            print("⚠️ ONNX 세션이 초기화되지 않았습니다")
            completion(nil)
            return
        }

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else {
                completion(nil)
                return
            }

            do {
                // 이미지 전처리
                let pixelValues = self.preprocessImage(image)
                let pixelMask = self.createPixelMask()
                let (inputIds, attentionMask, tokenTypeIds) = self.createTextInputs()

                // 입력 텐서 생성
                let inputs = try self.createInputTensors(
                    pixelValues: pixelValues,
                    pixelMask: pixelMask,
                    inputIds: inputIds,
                    attentionMask: attentionMask,
                    tokenTypeIds: tokenTypeIds
                )

                // 추론 실행
                let outputs = try session.run(
                    withInputs: inputs,
                    outputNames: ["logits", "pred_boxes"],
                    runOptions: nil
                )

                // 결과 처리
                if let bbox = self.postprocess(outputs: outputs) {
                    DispatchQueue.main.async {
                        completion(bbox)
                    }
                } else {
                    DispatchQueue.main.async {
                        completion(nil)
                    }
                }

            } catch {
                print("❌ ONNX 추론 실패: \(error)")
                DispatchQueue.main.async {
                    completion(nil)
                }
            }
        }
    }

    // MARK: - Image Preprocessing (🔥 Accelerate 최적화 + CIContext 재사용)
    private func preprocessImage(_ image: CIImage) -> [Float] {
        // 🔥 [수정 3] 클래스 멤버 ciContext 사용 (매번 생성하지 않음)
        let context = self.ciContext
        
        let pixelCount = inputSize * inputSize

        // 800x800으로 리사이즈
        let scale = CGFloat(inputSize) / max(image.extent.width, image.extent.height)
        let scaledImage = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))

        // 중앙 크롭
        let cropRect = CGRect(
            x: (scaledImage.extent.width - CGFloat(inputSize)) / 2,
            y: (scaledImage.extent.height - CGFloat(inputSize)) / 2,
            width: CGFloat(inputSize),
            height: CGFloat(inputSize)
        )
        let croppedImage = scaledImage.cropped(to: cropRect)

        // CGImage로 변환
        guard let cgImage = context.createCGImage(croppedImage, from: croppedImage.extent) else {
            return [Float](repeating: 0, count: 3 * pixelCount)
        }

        // 픽셀 데이터 추출
        let width = cgImage.width
        let height = cgImage.height
        var pixelData = [UInt8](repeating: 0, count: width * height * 4)

        let colorSpace = CGColorSpaceCreateDeviceRGB()
        guard let cgContext = CGContext(
            data: &pixelData,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else {
            return [Float](repeating: 0, count: 3 * pixelCount)
        }

        cgContext.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))

        // 🔥 vDSP 기반 고속 정규화 (ImageNet 평균/표준편차)
        let mean: [Float] = [0.485, 0.456, 0.406]
        let std: [Float] = [0.229, 0.224, 0.225]

        var result = [Float](repeating: 0, count: 3 * pixelCount)

        // 각 채널별 병렬 처리
        DispatchQueue.concurrentPerform(iterations: 3) { c in
            var channelData = [Float](repeating: 0, count: pixelCount)

            // RGBA에서 해당 채널 추출
            for i in 0..<pixelCount {
                channelData[i] = Float(pixelData[i * 4 + c])
            }

            // vDSP: /255.0 정규화
            var scale: Float = 1.0 / 255.0
            vDSP_vsmul(channelData, 1, &scale, &channelData, 1, vDSP_Length(pixelCount))

            // vDSP: (x - mean)
            var negMean = -mean[c]
            vDSP_vsadd(channelData, 1, &negMean, &channelData, 1, vDSP_Length(pixelCount))

            // vDSP: / std
            var invStd = 1.0 / std[c]
            vDSP_vsmul(channelData, 1, &invStd, &channelData, 1, vDSP_Length(pixelCount))

            // CHW 포맷으로 복사
            let offset = c * pixelCount
            for i in 0..<pixelCount {
                result[offset + i] = channelData[i]
            }
        }

        return result
    }

    // MARK: - Create Pixel Mask
    private func createPixelMask() -> [Int64] {
        // 모든 픽셀이 유효함을 나타내는 마스크
        return [Int64](repeating: 1, count: inputSize * inputSize)
    }

    // MARK: - Create Text Inputs
    private func createTextInputs() -> ([Int64], [Int64], [Int64]) {
        // "person" 검출을 위한 고정 토큰
        let inputIds = personTokenIds
        let attentionMask = [Int64](repeating: 1, count: personTokenIds.count)
        let tokenTypeIds = [Int64](repeating: 0, count: personTokenIds.count)

        return (inputIds, attentionMask, tokenTypeIds)
    }

    // MARK: - Create Input Tensors
    private func createInputTensors(
        pixelValues: [Float],
        pixelMask: [Int64],
        inputIds: [Int64],
        attentionMask: [Int64],
        tokenTypeIds: [Int64]
    ) throws -> [String: ORTValue] {

        var inputs = [String: ORTValue]()

        // pixel_values: [1, 3, 800, 800]
        let pixelValuesData = Data(bytes: pixelValues, count: pixelValues.count * MemoryLayout<Float>.size)
        let pixelValuesTensor = try ORTValue(
            tensorData: NSMutableData(data: pixelValuesData),
            elementType: .float,
            shape: [1, 3, NSNumber(value: inputSize), NSNumber(value: inputSize)]
        )
        inputs["pixel_values"] = pixelValuesTensor

        // pixel_mask: [1, 800, 800]
        let pixelMaskData = Data(bytes: pixelMask, count: pixelMask.count * MemoryLayout<Int64>.size)
        let pixelMaskTensor = try ORTValue(
            tensorData: NSMutableData(data: pixelMaskData),
            elementType: .int64,
            shape: [1, NSNumber(value: inputSize), NSNumber(value: inputSize)]
        )
        inputs["pixel_mask"] = pixelMaskTensor

        // input_ids: [1, seq_len]
        let seqLen = inputIds.count
        let inputIdsData = Data(bytes: inputIds, count: seqLen * MemoryLayout<Int64>.size)
        let inputIdsTensor = try ORTValue(
            tensorData: NSMutableData(data: inputIdsData),
            elementType: .int64,
            shape: [1, NSNumber(value: seqLen)]
        )
        inputs["input_ids"] = inputIdsTensor

        // attention_mask: [1, seq_len]
        let attentionMaskData = Data(bytes: attentionMask, count: seqLen * MemoryLayout<Int64>.size)
        let attentionMaskTensor = try ORTValue(
            tensorData: NSMutableData(data: attentionMaskData),
            elementType: .int64,
            shape: [1, NSNumber(value: seqLen)]
        )
        inputs["attention_mask"] = attentionMaskTensor

        // token_type_ids: [1, seq_len]
        let tokenTypeIdsData = Data(bytes: tokenTypeIds, count: seqLen * MemoryLayout<Int64>.size)
        let tokenTypeIdsTensor = try ORTValue(
            tensorData: NSMutableData(data: tokenTypeIdsData),
            elementType: .int64,
            shape: [1, NSNumber(value: seqLen)]
        )
        inputs["token_type_ids"] = tokenTypeIdsTensor

        return inputs
    }

    // MARK: - Postprocessing
    private func postprocess(outputs: [String: ORTValue]) -> CGRect? {
        guard let logitsValue = outputs["logits"],
              let boxesValue = outputs["pred_boxes"] else {
            return nil
        }

        do {
            // logits: [1, num_queries, num_classes]
            let logitsData = try logitsValue.tensorData() as Data
            let logits = logitsData.withUnsafeBytes { ptr in
                Array(ptr.bindMemory(to: Float.self))
            }

            // pred_boxes: [1, num_queries, 4] (cx, cy, w, h) normalized
            let boxesData = try boxesValue.tensorData() as Data
            let boxes = boxesData.withUnsafeBytes { ptr in
                Array(ptr.bindMemory(to: Float.self))
            }

            // 최고 confidence person 찾기
            let numQueries = 900  // Grounding DINO default
            var bestScore: Float = 0.6  // threshold
            var bestBox: CGRect?

            for i in 0..<numQueries {
                // sigmoid 적용
                let score = 1.0 / (1.0 + exp(-logits[i]))

                if score > bestScore {
                    bestScore = score

                    let cx = boxes[i * 4 + 0]
                    let cy = boxes[i * 4 + 1]
                    let w = boxes[i * 4 + 2]
                    let h = boxes[i * 4 + 3]

                    // (cx, cy, w, h) -> (x, y, w, h)
                    bestBox = CGRect(
                        x: CGFloat(cx - w/2),
                        y: CGFloat(cy - h/2),
                        width: CGFloat(w),
                        height: CGFloat(h)
                    )
                }
            }

            if let box = bestBox {
                print("✅ Person detected: score=\(bestScore), box=\(box)")
            }

            return bestBox

        } catch {
            print("❌ 출력 처리 실패: \(error)")
            return nil
        }
    }

    // MARK: - Detect All Persons
    func detectAllPersons(in image: CIImage, completion: @escaping ([Detection]) -> Void) {
        guard let session = ortSession else {
            completion([])
            return
        }

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else {
                completion([])
                return
            }

            do {
                let pixelValues = self.preprocessImage(image)
                let pixelMask = self.createPixelMask()
                let (inputIds, attentionMask, tokenTypeIds) = self.createTextInputs()

                let inputs = try self.createInputTensors(
                    pixelValues: pixelValues,
                    pixelMask: pixelMask,
                    inputIds: inputIds,
                    attentionMask: attentionMask,
                    tokenTypeIds: tokenTypeIds
                )

                let outputs = try session.run(
                    withInputs: inputs,
                    outputNames: ["logits", "pred_boxes"],
                    runOptions: nil
                )

                let detections = self.postprocessMultiple(outputs: outputs)
                DispatchQueue.main.async {
                    completion(detections)
                }

            } catch {
                print("❌ ONNX 추론 실패: \(error)")
                DispatchQueue.main.async {
                    completion([])
                }
            }
        }
    }

    private func postprocessMultiple(outputs: [String: ORTValue]) -> [Detection] {
        guard let logitsValue = outputs["logits"],
              let boxesValue = outputs["pred_boxes"] else {
            return []
        }

        do {
            let logitsData = try logitsValue.tensorData() as Data
            let logits = logitsData.withUnsafeBytes { ptr in
                Array(ptr.bindMemory(to: Float.self))
            }

            let boxesData = try boxesValue.tensorData() as Data
            let boxes = boxesData.withUnsafeBytes { ptr in
                Array(ptr.bindMemory(to: Float.self))
            }

            var detections = [Detection]()
            let numQueries = 900
            let threshold: Float = 0.5

            for i in 0..<numQueries {
                let score = 1.0 / (1.0 + exp(-logits[i]))

                if score > threshold {
                    let cx = boxes[i * 4 + 0]
                    let cy = boxes[i * 4 + 1]
                    let w = boxes[i * 4 + 2]
                    let h = boxes[i * 4 + 3]

                    let bbox = CGRect(
                        x: CGFloat(cx - w/2),
                        y: CGFloat(cy - h/2),
                        width: CGFloat(w),
                        height: CGFloat(h)
                    )

                    detections.append(Detection(
                        label: "person",
                        confidence: score,
                        boundingBox: bbox
                    ))
                }
            }

            // NMS (Non-Maximum Suppression)
            return nonMaximumSuppression(detections, iouThreshold: 0.5)

        } catch {
            return []
        }
    }

    // MARK: - NMS
    private func nonMaximumSuppression(_ detections: [Detection], iouThreshold: Float) -> [Detection] {
        guard !detections.isEmpty else { return [] }

        var sorted = detections.sorted { $0.confidence > $1.confidence }
        var result = [Detection]()

        while !sorted.isEmpty {
            let best = sorted.removeFirst()
            result.append(best)

            sorted = sorted.filter { detection in
                let iou = calculateIoU(best.boundingBox, detection.boundingBox)
                return iou < iouThreshold
            }
        }

        return result
    }

    private func calculateIoU(_ a: CGRect, _ b: CGRect) -> Float {
        let intersection = a.intersection(b)
        if intersection.isNull { return 0 }

        let intersectionArea = intersection.width * intersection.height
        let unionArea = a.width * a.height + b.width * b.height - intersectionArea

        return Float(intersectionArea / unionArea)
    }
}
