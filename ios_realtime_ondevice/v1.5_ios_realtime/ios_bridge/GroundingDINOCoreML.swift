// GroundingDINOCoreML.swift
// Grounding DINO CoreML 구현
// 작성일: 2025-12-05

import CoreML
import Vision
import CoreImage

class GroundingDINOCoreML {
    private var model: VNCoreMLModel?
    private let modelURL: URL

    // MARK: - Initialization
    init() {
        // 모델 경로 설정
        guard let url = Bundle.main.url(forResource: "GroundingDINO", withExtension: "mlmodelc") else {
            print("❌ Grounding DINO 모델 파일을 찾을 수 없습니다")
            self.modelURL = URL(fileURLWithPath: "")
            return
        }
        self.modelURL = url

        // 모델 로드
        loadModel()
    }

    private func loadModel() {
        do {
            let mlModel = try MLModel(contentsOf: modelURL)
            self.model = try VNCoreMLModel(for: mlModel)
            print("✅ Grounding DINO 모델 로드 성공")
        } catch {
            print("❌ Grounding DINO 모델 로드 실패: \(error)")
        }
    }

    // MARK: - Person Detection
    func detectPerson(in image: CIImage, completion: @escaping (CGRect?) -> Void) {
        guard let model = model else {
            print("⚠️ 모델이 로드되지 않았습니다. 폴백 모드 사용")
            // 폴백: Vision framework의 기본 person detection
            detectPersonWithVision(in: image, completion: completion)
            return
        }

        // Grounding DINO request 생성
        let request = VNCoreMLRequest(model: model) { request, error in
            if let error = error {
                print("❌ Grounding DINO 검출 실패: \(error)")
                completion(nil)
                return
            }

            // 결과 처리
            if let results = request.results as? [VNRecognizedObjectObservation] {
                // "person" 클래스 찾기
                let personResults = results.filter { observation in
                    observation.labels.contains { $0.identifier == "person" && $0.confidence > 0.5 }
                }

                if let bestPerson = personResults.first {
                    completion(bestPerson.boundingBox)
                } else {
                    completion(nil)
                }
            }
        }

        // 이미지 처리
        let handler = VNImageRequestHandler(ciImage: image, options: [:])
        do {
            try handler.perform([request])
        } catch {
            print("❌ 이미지 처리 실패: \(error)")
            completion(nil)
        }
    }

    // MARK: - Fallback with Vision Framework
    private func detectPersonWithVision(in image: CIImage, completion: @escaping (CGRect?) -> Void) {
        // Vision framework의 기본 person detection 사용
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

        let handler = VNImageRequestHandler(ciImage: image, options: [:])
        do {
            try handler.perform([request])
        } catch {
            print("❌ Vision 처리 실패: \(error)")
            completion(nil)
        }
    }

    // MARK: - Text-Guided Detection (Advanced)
    func detectWithText(in image: CIImage, text: String, completion: @escaping ([Detection]) -> Void) {
        // 텍스트 기반 검출 (Grounding DINO의 핵심 기능)
        // CoreML 변환시 텍스트 인코더 포함 필요

        guard let model = model else {
            print("⚠️ 텍스트 기반 검출은 모델 변환 후 사용 가능")
            completion([])
            return
        }

        // TODO: 텍스트 인코딩 및 검출
        // 현재는 기본 person detection으로 대체
        detectPerson(in: image) { bbox in
            if let bbox = bbox {
                let detection = Detection(
                    label: "person",
                    confidence: 0.9,
                    boundingBox: bbox
                )
                completion([detection])
            } else {
                completion([])
            }
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
    func analyzeFraming(personBBox: CGRect, imageSize: CGSize) -> FramingAnalysis {
        let margins = calculateMargins(personBBox: personBBox, imageSize: imageSize)

        // 프레이밍 타입 결정
        let framingType: FramingType
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

        return FramingAnalysis(
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

struct FramingAnalysis {
    let type: FramingType
    let score: CGFloat
    let hasCropIssue: Bool
    let margins: MarginAnalysis
}

enum FramingType {
    case tooTight
    case tooLoose
    case closeUp
    case medium
    case wide
}