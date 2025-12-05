//
//  TryAngleBridge.swift
//  TryAngle iOS Realtime Bridge
//  작성일: 2025-12-05
//  Python 백엔드와 iOS 앱 연결
//

import Foundation
import UIKit
import AVFoundation
import Vision

// MARK: - Bridge Protocol
protocol TryAngleBridgeDelegate: AnyObject {
    func tryAngleBridge(_ bridge: TryAngleBridge, didReceiveFeedback feedback: TryAngleFeedback)
    func tryAngleBridge(_ bridge: TryAngleBridge, didUpdatePerformance stats: PerformanceStats)
    func tryAngleBridge(_ bridge: TryAngleBridge, didEncounterError error: Error)
}

// MARK: - Data Models
struct TryAngleFeedback {
    let frameId: Int
    let primary: String
    let suggestions: [String]
    let movement: MovementGuide?
    let compressionInfo: CompressionInfo?
    let processingLevel: Int
    let timestamp: TimeInterval
}

struct MovementGuide {
    let direction: String
    let arrow: String
    let amount: String
}

struct CompressionInfo {
    let index: Float
    let cameraType: String
    let suggestion: String?
}

struct PerformanceStats {
    let fps: Float
    let avgProcessingTime: Float
    let skipRate: Float
    let queueSize: Int
}

// MARK: - Main Bridge Class
class TryAngleBridge: NSObject {

    // MARK: Properties
    weak var delegate: TryAngleBridgeDelegate?

    private let serverURL: URL
    private var session: URLSession!
    private var processingQueue = DispatchQueue(label: "com.tryangle.processing", qos: .userInitiated)
    private var frameCounter = 0
    private var isProcessing = false

    // Reference image cache
    private var referenceId: String?
    private var referenceAnalysis: [String: Any]?

    // Performance tracking
    private var performanceTimer: Timer?
    private var recentProcessingTimes: [TimeInterval] = []

    // Frame skipping
    private var skipLevel = 0
    private let targetFPS: Float = 30.0

    // MARK: Initialization
    init(serverURL: URL = URL(string: "http://localhost:8000")!) {
        self.serverURL = serverURL
        super.init()

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 1.0
        config.timeoutIntervalForResource = 5.0
        self.session = URLSession(configuration: config)
    }

    // MARK: - Public Methods

    /// 레퍼런스 이미지 분석
    func analyzeReference(image: UIImage, completion: @escaping (Result<String, Error>) -> Void) {
        guard let imageData = image.jpegData(compressionQuality: 0.9) else {
            completion(.failure(BridgeError.invalidImage))
            return
        }

        processingQueue.async { [weak self] in
            self?.uploadReference(imageData: imageData, completion: completion)
        }
    }

    /// 실시간 프레임 처리
    func processFrame(_ pixelBuffer: CVPixelBuffer) {
        // 프레임 스킵 체크
        frameCounter += 1
        if shouldSkipFrame() {
            return
        }

        // 이미 처리 중이면 스킵
        guard !isProcessing else { return }
        isProcessing = true

        processingQueue.async { [weak self] in
            guard let self = self else { return }

            // CVPixelBuffer를 UIImage로 변환
            let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
            let context = CIContext()
            guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else {
                self.isProcessing = false
                return
            }

            let uiImage = UIImage(cgImage: cgImage)

            // JPEG 압축 (품질 조정으로 속도 최적화)
            guard let imageData = uiImage.jpegData(compressionQuality: 0.7) else {
                self.isProcessing = false
                return
            }

            // 서버로 전송
            let startTime = Date()
            self.processFrameOnServer(imageData: imageData) { [weak self] result in
                let processingTime = Date().timeIntervalSince(startTime)

                self?.updatePerformanceStats(processingTime: processingTime)
                self?.isProcessing = false

                switch result {
                case .success(let feedback):
                    DispatchQueue.main.async {
                        self?.delegate?.tryAngleBridge(self!, didReceiveFeedback: feedback)
                    }
                case .failure(let error):
                    DispatchQueue.main.async {
                        self?.delegate?.tryAngleBridge(self!, didEncounterError: error)
                    }
                }
            }
        }
    }

    /// 성능 통계 시작
    func startPerformanceMonitoring() {
        performanceTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.reportPerformanceStats()
        }
    }

    /// 성능 통계 중지
    func stopPerformanceMonitoring() {
        performanceTimer?.invalidate()
        performanceTimer = nil
    }

    // MARK: - Private Methods

    private func shouldSkipFrame() -> Bool {
        // 적응형 프레임 스킵
        switch skipLevel {
        case 0:
            return false // 모든 프레임 처리
        case 1:
            return frameCounter % 2 != 0 // 2프레임 중 1개 스킵
        case 2:
            return frameCounter % 3 != 0 // 3프레임 중 2개 스킵
        default:
            return frameCounter % 4 != 0 // 4프레임 중 3개 스킵
        }
    }

    private func uploadReference(imageData: Data, completion: @escaping (Result<String, Error>) -> Void) {
        var request = URLRequest(url: serverURL.appendingPathComponent("analyze_reference"))
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"image\"; filename=\"reference.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        session.dataTask(with: request) { [weak self] data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let refId = json["reference_id"] as? String else {
                completion(.failure(BridgeError.invalidResponse))
                return
            }

            self?.referenceId = refId
            self?.referenceAnalysis = json["analysis"] as? [String: Any]
            completion(.success(refId))
        }.resume()
    }

    private func processFrameOnServer(imageData: Data, completion: @escaping (Result<TryAngleFeedback, Error>) -> Void) {
        var request = URLRequest(url: serverURL.appendingPathComponent("process_frame"))
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()

        // 이미지 데이터
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n".data(using: .utf8)!)

        // 레퍼런스 ID (있는 경우)
        if let refId = referenceId {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"ref_id\"\r\n\r\n".data(using: .utf8)!)
            body.append(refId.data(using: .utf8)!)
            body.append("\r\n".data(using: .utf8)!)
        }

        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        session.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                completion(.failure(BridgeError.invalidResponse))
                return
            }

            // 피드백 파싱
            let feedback = self.parseFeedback(json)
            completion(.success(feedback))
        }.resume()
    }

    private func parseFeedback(_ json: [String: Any]) -> TryAngleFeedback {
        let feedbackData = json["feedback"] as? [String: Any] ?? [:]

        // Movement guide 파싱
        var movement: MovementGuide?
        if let moveData = feedbackData["movement"] as? [String: Any] {
            movement = MovementGuide(
                direction: moveData["direction"] as? String ?? "",
                arrow: moveData["arrow"] as? String ?? "",
                amount: moveData["amount"] as? String ?? ""
            )
        }

        // Compression info 파싱
        var compression: CompressionInfo?
        if let compData = json["depth_info"] as? [String: Any] {
            compression = CompressionInfo(
                index: compData["compression_index"] as? Float ?? 0.5,
                cameraType: compData["camera_type"] as? String ?? "normal",
                suggestion: compData["suggestion"] as? String
            )
        }

        return TryAngleFeedback(
            frameId: json["frame_id"] as? Int ?? frameCounter,
            primary: feedbackData["primary"] as? String ?? "",
            suggestions: feedbackData["suggestions"] as? [String] ?? [],
            movement: movement,
            compressionInfo: compression,
            processingLevel: json["processing_level"] as? Int ?? 1,
            timestamp: Date().timeIntervalSince1970
        )
    }

    private func updatePerformanceStats(processingTime: TimeInterval) {
        recentProcessingTimes.append(processingTime)
        if recentProcessingTimes.count > 10 {
            recentProcessingTimes.removeFirst()
        }

        // 적응형 스킵 레벨 조정
        let avgTime = recentProcessingTimes.reduce(0, +) / Double(recentProcessingTimes.count)
        let targetTime = 1.0 / Double(targetFPS)

        if avgTime < targetTime * 0.7 {
            skipLevel = max(0, skipLevel - 1)
        } else if avgTime > targetTime * 1.2 {
            skipLevel = min(3, skipLevel + 1)
        }
    }

    private func reportPerformanceStats() {
        let avgTime = recentProcessingTimes.isEmpty ? 0 :
            recentProcessingTimes.reduce(0, +) / Double(recentProcessingTimes.count)

        let effectiveFPS: Float
        switch skipLevel {
        case 0: effectiveFPS = targetFPS
        case 1: effectiveFPS = targetFPS / 2
        case 2: effectiveFPS = targetFPS / 3
        default: effectiveFPS = targetFPS / 4
        }

        let stats = PerformanceStats(
            fps: effectiveFPS,
            avgProcessingTime: Float(avgTime * 1000),
            skipRate: Float(skipLevel) / 3.0,
            queueSize: 0
        )

        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.delegate?.tryAngleBridge(self, didUpdatePerformance: stats)
        }
    }
}

// MARK: - Error Types
enum BridgeError: LocalizedError {
    case invalidImage
    case invalidResponse
    case serverUnavailable
    case processingTimeout

    var errorDescription: String? {
        switch self {
        case .invalidImage:
            return "Invalid image format"
        case .invalidResponse:
            return "Invalid server response"
        case .serverUnavailable:
            return "Server is unavailable"
        case .processingTimeout:
            return "Processing timeout"
        }
    }
}

// MARK: - Camera Integration Example
class TryAngleCameraViewController: UIViewController {

    private let bridge = TryAngleBridge()
    private var captureSession: AVCaptureSession!
    private var videoOutput: AVCaptureVideoDataOutput!
    private var previewLayer: AVCaptureVideoPreviewLayer!

    // UI Elements
    private let feedbackLabel = UILabel()
    private let movementIndicator = UIImageView()
    private let performanceLabel = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()
        setupCamera()
        setupUI()
        bridge.delegate = self
        bridge.startPerformanceMonitoring()
    }

    private func setupCamera() {
        captureSession = AVCaptureSession()
        captureSession.sessionPreset = .hd1280x720

        guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: camera) else { return }

        captureSession.addInput(input)

        videoOutput = AVCaptureVideoDataOutput()
        videoOutput.setSampleBufferDelegate(self, queue: DispatchQueue(label: "video.queue"))
        videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]

        captureSession.addOutput(videoOutput)

        previewLayer = AVCaptureVideoPreviewLayer(session: captureSession)
        previewLayer.videoGravity = .resizeAspectFill
        previewLayer.frame = view.bounds
        view.layer.insertSublayer(previewLayer, at: 0)

        captureSession.startRunning()
    }

    private func setupUI() {
        // Feedback label
        feedbackLabel.translatesAutoresizingMaskIntoConstraints = false
        feedbackLabel.textColor = .white
        feedbackLabel.backgroundColor = UIColor.black.withAlphaComponent(0.7)
        feedbackLabel.numberOfLines = 0
        feedbackLabel.textAlignment = .center
        feedbackLabel.layer.cornerRadius = 10
        feedbackLabel.clipsToBounds = true
        view.addSubview(feedbackLabel)

        // Performance label
        performanceLabel.translatesAutoresizingMaskIntoConstraints = false
        performanceLabel.textColor = .green
        performanceLabel.font = .systemFont(ofSize: 12)
        performanceLabel.backgroundColor = UIColor.black.withAlphaComponent(0.5)
        view.addSubview(performanceLabel)

        NSLayoutConstraint.activate([
            feedbackLabel.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -20),
            feedbackLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            feedbackLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),

            performanceLabel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 20),
            performanceLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20)
        ])
    }
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate
extension TryAngleCameraViewController: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        bridge.processFrame(pixelBuffer)
    }
}

// MARK: - TryAngleBridgeDelegate
extension TryAngleCameraViewController: TryAngleBridgeDelegate {
    func tryAngleBridge(_ bridge: TryAngleBridge, didReceiveFeedback feedback: TryAngleFeedback) {
        var feedbackText = feedback.primary

        if let movement = feedback.movement {
            feedbackText += "\n\(movement.arrow) \(movement.direction) \(movement.amount)"
        }

        if !feedback.suggestions.isEmpty {
            feedbackText += "\n" + feedback.suggestions.joined(separator: "\n")
        }

        feedbackLabel.text = feedbackText
    }

    func tryAngleBridge(_ bridge: TryAngleBridge, didUpdatePerformance stats: PerformanceStats) {
        performanceLabel.text = String(format: "FPS: %.1f | %.1fms", stats.fps, stats.avgProcessingTime)
    }

    func tryAngleBridge(_ bridge: TryAngleBridge, didEncounterError error: Error) {
        print("Error: \(error.localizedDescription)")
    }
}