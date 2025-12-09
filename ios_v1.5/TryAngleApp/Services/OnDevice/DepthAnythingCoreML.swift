//
//  DepthAnythingCoreML.swift
//  Depth Anything CoreML Integration
//  작성일: 2025-12-05
//

import Foundation
import CoreML
import Vision
import UIKit

// MARK: - Depth Anything CoreML Wrapper
class DepthAnythingCoreML {

    private var model: VNCoreMLModel?
    private let modelType: ModelType

    enum ModelType {
        case small
        case base

        var modelName: String {
            switch self {
            case .small: return "DepthAnythingV2SmallF16"
            case .base: return "DepthAnythingV2SmallF16"  // 같은 모델 사용
            }
        }
    }

    init(modelType: ModelType = .small) {
        self.modelType = modelType
        setupModel()
    }

    // MARK: - 모델 설정
    private func setupModel() {
        // 방법 1: Apple 공식 CoreML 모델 사용 (다운로드 필요)
        // https://huggingface.co/apple/coreml-depth-anything-v2-small

        guard let modelURL = Bundle.main.url(forResource: modelType.modelName, withExtension: "mlmodelc") else {
            print("❌ Depth Anything 모델 파일을 찾을 수 없습니다")
            print("   다운로드: https://huggingface.co/apple/coreml-depth-anything-v2-small")
            return
        }

        do {
            let mlModel = try MLModel(contentsOf: modelURL)
            model = try VNCoreMLModel(for: mlModel)
            print("✅ Depth Anything CoreML 모델 로드 성공")
        } catch {
            print("❌ Depth Anything 모델 로드 실패: \(error)")
        }
    }

    // MARK: - 깊이 추정
    func estimateDepth(from image: UIImage, completion: @escaping (Result<V15DepthResult, Error>) -> Void) {
        guard let model = model else {
            completion(.failure(DepthError.modelNotLoaded))
            return
        }

        guard let cgImage = image.cgImage else {
            completion(.failure(DepthError.invalidImage))
            return
        }

        // Vision 요청 생성
        let request = VNCoreMLRequest(model: model) { request, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let results = request.results as? [VNCoreMLFeatureValueObservation],
                  let depthMap = results.first?.featureValue.multiArrayValue else {
                completion(.failure(DepthError.processingFailed))
                return
            }

            // 깊이맵 처리
            let result = self.processDepthMap(depthMap, originalImage: image)
            completion(.success(result))
        }

        // 입력 이미지 크기 설정 (518x518)
        request.imageCropAndScaleOption = .centerCrop

        // 요청 실행
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])

        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try handler.perform([request])
            } catch {
                completion(.failure(error))
            }
        }
    }

    // MARK: - 깊이맵 처리
    private func processDepthMap(_ depthMap: MLMultiArray, originalImage: UIImage) -> V15DepthResult {
        // 압축감 계산
        let compressionIndex = calculateCompression(from: depthMap)

        // 카메라 타입 판정
        let cameraType = determineCameraType(compression: compressionIndex)

        // 깊이맵을 이미지로 변환 (옵션)
        let depthImage = convertToImage(depthMap)

        return V15DepthResult(
            depthMap: depthMap,
            depthImage: depthImage,
            compressionIndex: compressionIndex,
            cameraType: cameraType
        )
    }

    // MARK: - 압축감 계산
    private func calculateCompression(from depthMap: MLMultiArray) -> Float {
        // 깊이맵에서 전경과 배경의 깊이 차이 계산
        let shape = depthMap.shape
        let height = shape[0].intValue
        let width = shape[1].intValue

        var foregroundDepth: Float = 0
        var backgroundDepth: Float = 0

        // 상단 1/3 (배경)
        for y in 0..<(height/3) {
            for x in 0..<width {
                let index = y * width + x
                backgroundDepth += depthMap[index].floatValue
            }
        }
        backgroundDepth /= Float(height * width / 3)

        // 하단 1/4 (전경)
        for y in (3*height/4)..<height {
            for x in 0..<width {
                let index = y * width + x
                foregroundDepth += depthMap[index].floatValue
            }
        }
        foregroundDepth /= Float(height * width / 4)

        // 압축감 지수 (0=광각, 1=망원)
        let depthRange = abs(backgroundDepth - foregroundDepth)
        let compressionIndex = 1.0 - min(depthRange * 2, 1.0)

        return compressionIndex
    }

    // MARK: - 카메라 타입 판정
    private func determineCameraType(compression: Float) -> V15CameraType {
        switch compression {
        case ..<0.3:
            return .wide
        case 0.3..<0.5:
            return .normal
        case 0.5..<0.7:
            return .semiTele
        default:
            return .telephoto
        }
    }

    // MARK: - 깊이맵을 이미지로 변환
    private func convertToImage(_ depthMap: MLMultiArray) -> UIImage? {
        let shape = depthMap.shape
        let height = shape[0].intValue
        let width = shape[1].intValue

        // 정규화
        var minDepth = Float.greatestFiniteMagnitude
        var maxDepth = Float.leastNormalMagnitude

        for i in 0..<depthMap.count {
            let value = depthMap[i].floatValue
            minDepth = min(minDepth, value)
            maxDepth = max(maxDepth, value)
        }

        let range = maxDepth - minDepth

        // 그레이스케일 이미지 생성
        var pixels = [UInt8]()
        for i in 0..<depthMap.count {
            let normalized = (depthMap[i].floatValue - minDepth) / range
            pixels.append(UInt8(normalized * 255))
        }

        // CGImage 생성
        let colorSpace = CGColorSpaceCreateDeviceGray()
        guard let context = CGContext(
            data: &pixels,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.none.rawValue
        ) else { return nil }

        guard let cgImage = context.makeImage() else { return nil }
        return UIImage(cgImage: cgImage)
    }
}

// MARK: - 결과 구조체 (v1.5 전용 - 기존 DepthResult와 충돌 방지)
struct V15DepthResult {
    let depthMap: MLMultiArray
    let depthImage: UIImage?
    let compressionIndex: Float
    let cameraType: V15CameraType
}

enum V15CameraType {
    case wide       // 광각 (24-35mm)
    case normal     // 표준 (35-50mm)
    case semiTele   // 준망원 (50-85mm)
    case telephoto  // 망원 (85mm+)

    var description: String {
        switch self {
        case .wide: return "광각"
        case .normal: return "표준"
        case .semiTele: return "준망원"
        case .telephoto: return "망원"
        }
    }

    var recommendation: String? {
        switch self {
        case .wide: return "더 가까이 접근하거나 망원 렌즈 사용"
        case .normal: return nil
        case .semiTele: return nil
        case .telephoto: return "강한 압축감 - 광각 렌즈 고려"
        }
    }
}

// MARK: - 에러 타입
enum DepthError: LocalizedError {
    case modelNotLoaded
    case invalidImage
    case processingFailed

    var errorDescription: String? {
        switch self {
        case .modelNotLoaded:
            return "Depth Anything 모델이 로드되지 않았습니다"
        case .invalidImage:
            return "유효하지 않은 이미지입니다"
        case .processingFailed:
            return "깊이 추정 처리 실패"
        }
    }
}

// MARK: - 사용 예시
class DepthAnythingExample {

    let depthEstimator = DepthAnythingCoreML(modelType: .small)

    func analyzeImage(_ image: UIImage) {
        depthEstimator.estimateDepth(from: image) { result in
            switch result {
            case .success(let depthResult):
                print("✅ 깊이 추정 성공")
                print("   압축감: \(depthResult.compressionIndex)")
                print("   카메라 타입: \(depthResult.cameraType.description)")
                print("   추천: \(depthResult.cameraType.recommendation)")

                // 깊이맵 이미지 표시
                if let depthImage = depthResult.depthImage {
                    // UI 업데이트
                }

            case .failure(let error):
                print("❌ 깊이 추정 실패: \(error)")
            }
        }
    }
}