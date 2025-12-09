// GroundingDINOCoreML.swift
// Grounding DINO 통합 인터페이스
// ONNX Runtime 사용 + Vision Framework 폴백
// 작성일: 2025-12-05
// 수정일: 2025-12-06 - ONNX Runtime 지원 추가

import CoreML
import Vision
import CoreImage

class GroundingDINOCoreML {

    // ONNX 모델 인스턴스
    private var onnxModel: GroundingDINOONNX?
    private var useONNX: Bool = false

    // MARK: - Initialization
    init() {
        // ONNX 모델 초기화 시도
        let onnx = GroundingDINOONNX()

        // ONNX 세션이 실제로 로드되었는지 확인
        if onnx.isSessionLoaded {
            onnxModel = onnx
            useONNX = true
            print("✅ Grounding DINO 초기화 완료 (ONNX Runtime)")
        } else {
            onnxModel = nil
            useONNX = false
            print("⚠️ ONNX 세션 로드 실패, Vision Framework 폴백 사용")
        }
    }

    // MARK: - Person Detection
    func detectPerson(in image: CIImage, completion: @escaping (CGRect?) -> Void) {
        if useONNX, let onnx = onnxModel {
            // ONNX Runtime 사용
            onnx.detectPerson(in: image, completion: completion)
        } else {
            // Vision Framework 폴백
            detectPersonWithVision(in: image, completion: completion)
        }
    }

    // MARK: - Vision Framework Fallback
    private func detectPersonWithVision(in image: CIImage, completion: @escaping (CGRect?) -> Void) {
        let request = VNDetectHumanRectanglesRequest { request, error in
            if let error = error {
                print("❌ Vision person detection 실패: \(error)")
                completion(nil)
                return
            }

            if let results = request.results as? [VNHumanObservation],
               let firstPerson = results.first {
                completion(firstPerson.boundingBox)
            } else {
                completion(nil)
            }
        }

        request.upperBodyOnly = false

        let handler = VNImageRequestHandler(ciImage: image, options: [:])
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try handler.perform([request])
            } catch {
                print("❌ Vision 처리 실패: \(error)")
                DispatchQueue.main.async {
                    completion(nil)
                }
            }
        }
    }

    // MARK: - Multiple Person Detection
    func detectAllPersons(in image: CIImage, completion: @escaping ([Detection]) -> Void) {
        if useONNX, let onnx = onnxModel {
            onnx.detectAllPersons(in: image, completion: completion)
        } else {
            detectAllPersonsWithVision(in: image, completion: completion)
        }
    }

    private func detectAllPersonsWithVision(in image: CIImage, completion: @escaping ([Detection]) -> Void) {
        let request = VNDetectHumanRectanglesRequest { request, error in
            if let error = error {
                print("❌ Vision person detection 실패: \(error)")
                completion([])
                return
            }

            if let results = request.results as? [VNHumanObservation] {
                let detections = results.map { observation in
                    Detection(
                        label: "person",
                        confidence: observation.confidence,
                        boundingBox: observation.boundingBox
                    )
                }
                completion(detections)
            } else {
                completion([])
            }
        }

        request.upperBodyOnly = false

        let handler = VNImageRequestHandler(ciImage: image, options: [:])
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try handler.perform([request])
            } catch {
                print("❌ Vision 처리 실패: \(error)")
                DispatchQueue.main.async {
                    completion([])
                }
            }
        }
    }

    // MARK: - Text-Guided Detection
    func detectWithText(in image: CIImage, text: String, completion: @escaping ([Detection]) -> Void) {
        if text.lowercased().contains("person") || text.lowercased().contains("사람") {
            detectAllPersons(in: image, completion: completion)
        } else {
            print("⚠️ 현재 'person' 검출만 지원됩니다")
            completion([])
        }
    }

    // MARK: - Model Info
    var isUsingONNX: Bool {
        return useONNX
    }

    var modelDescription: String {
        if useONNX {
            return "Grounding DINO (ONNX Runtime)"
        } else {
            return "Vision Framework (VNDetectHumanRectanglesRequest)"
        }
    }
}

// MARK: - Detection Result
struct Detection {
    let label: String
    let confidence: Float
    let boundingBox: CGRect
}

// MARK: - Legacy System Port
extension GroundingDINOCoreML {

    // legacy_analyzer.py의 calculate_margins를 Swift로 포팅
    func calculateMargins(personBBox: CGRect, imageSize: CGSize) -> MarginAnalysis {
        let imageWidth = imageSize.width
        let imageHeight = imageSize.height

        // bbox를 픽셀 좌표로 변환 (Vision은 normalized coordinates 사용)
        let x = personBBox.origin.x * imageWidth
        let y = personBBox.origin.y * imageHeight
        let w = personBBox.width * imageWidth
        let h = personBBox.height * imageHeight

        // 여백 계산
        let leftMargin = x
        let rightMargin = imageWidth - (x + w)
        let topMargin = y
        let bottomMargin = imageHeight - (y + h)

        // 비율 계산
        let leftRatio = leftMargin / imageWidth
        let rightRatio = rightMargin / imageWidth
        let topRatio = topMargin / imageHeight
        let bottomRatio = bottomMargin / imageHeight

        // 균형 점수 계산
        let horizontalBalance = 1.0 - abs(leftRatio - rightRatio)
        let verticalBalance = 1.0 - abs(topRatio - bottomRatio * 0.5) // 하단 2:1 비율 선호
        let balanceScore = (horizontalBalance + verticalBalance) / 2.0

        return MarginAnalysis(
            left: leftMargin,
            right: rightMargin,
            top: topMargin,
            bottom: bottomMargin,
            leftRatio: leftRatio,
            rightRatio: rightRatio,
            topRatio: topRatio,
            bottomRatio: bottomRatio,
            balanceScore: balanceScore
        )
    }

    // 프레이밍 분석
    func analyzeFraming(personBBox: CGRect, imageSize: CGSize) -> V15FramingAnalysis {
        let margins = calculateMargins(personBBox: personBBox, imageSize: imageSize)

        // 프레이밍 타입 결정
        let framingType: V15FramingType
        let bboxHeightRatio = personBBox.height

        if bboxHeightRatio > 0.8 {
            framingType = .tooTight
        } else if bboxHeightRatio < 0.3 {
            framingType = .tooLoose
        } else if bboxHeightRatio > 0.6 {
            framingType = .closeUp
        } else if bboxHeightRatio > 0.4 {
            framingType = .medium
        } else {
            framingType = .wide
        }

        // 크롭 이슈 체크
        let hasCropIssue = margins.left < 10 || margins.right < 10 ||
                           margins.top < 10 || margins.bottom < 10

        return V15FramingAnalysis(
            type: framingType,
            score: margins.balanceScore,
            hasCropIssue: hasCropIssue,
            margins: margins
        )
    }
}

// MARK: - Data Structures
struct MarginAnalysis {
    let left: CGFloat
    let right: CGFloat
    let top: CGFloat
    let bottom: CGFloat
    let leftRatio: CGFloat
    let rightRatio: CGFloat
    let topRatio: CGFloat
    let bottomRatio: CGFloat
    let balanceScore: CGFloat
}

struct V15FramingAnalysis {
    let type: V15FramingType
    let score: CGFloat
    let hasCropIssue: Bool
    let margins: MarginAnalysis
}

enum V15FramingType {
    case tooTight
    case tooLoose
    case closeUp
    case medium
    case wide
}