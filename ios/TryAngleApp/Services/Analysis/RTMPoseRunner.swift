import Foundation
import UIImage
import CoreGraphics
import onnxruntime_mobile_c

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

    // 모델 경로
    private let detectorModelPath: String
    private let poseModelPath: String

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
        // 1. Environment 생성
        var status = OrtCreateEnv(ORT_LOGGING_LEVEL_WARNING, "RTMPose", &env)
        guard status == nil, env != nil else {
            print("❌ ONNX Runtime 환경 생성 실패")
            return
        }

        // 2. Session Options 설정
        var sessionOptions: OpaquePointer?
        status = OrtCreateSessionOptions(&sessionOptions)
        guard status == nil else {
            print("❌ Session options 생성 실패")
            return
        }

        // 그래프 최적화 활성화
        OrtSetSessionGraphOptimizationLevel(sessionOptions, ORT_ENABLE_ALL)

        // 🔥 CoreML Execution Provider 활성화 (Apple Neural Engine 사용)
        var coremlOptions: OpaquePointer?
        OrtCreateCoreMLProviderOptions(&coremlOptions)
        if let coremlOptions = coremlOptions {
            // ANE + GPU + CPU 모두 사용
            OrtSessionOptionsAppendExecutionProvider_CoreML(sessionOptions, coremlOptions)
            OrtReleaseCoreMLProviderOptions(coremlOptions)
            print("✅ CoreML Execution Provider 활성화 (ANE 가속)")
        }

        // 병렬 처리 설정
        OrtSetIntraOpNumThreads(sessionOptions, 4)
        OrtSetInterOpNumThreads(sessionOptions, 2)

        // 3. 세션 생성
        // Detector 세션
        status = OrtCreateSession(env, detectorModelPath, sessionOptions, &detectorSession)
        if status != nil || detectorSession == nil {
            print("❌ Detector 세션 생성 실패")
        } else {
            print("✅ YOLOX Detector 로드 성공")
        }

        // Pose 세션
        status = OrtCreateSession(env, poseModelPath, sessionOptions, &poseSession)
        if status != nil || poseSession == nil {
            print("❌ Pose 세션 생성 실패")
        } else {
            print("✅ RTMPose 로드 성공")
        }

        // Session options 해제
        if let opts = sessionOptions {
            OrtReleaseSessionOptions(opts)
        }
    }

    // MARK: - 정리
    private func cleanup() {
        if let session = detectorSession {
            OrtReleaseSession(session)
        }
        if let session = poseSession {
            OrtReleaseSession(session)
        }
        if let e = env {
            OrtReleaseEnv(e)
        }
    }

    // MARK: - 포즈 추정
    func detectPose(from image: UIImage) -> RTMPoseResult? {
        // TODO: 구현 예정
        // 1. YOLOX로 인물 검출
        // 2. 검출된 영역을 RTMPose로 포즈 추정
        // 3. 133개 키포인트 반환

        print("⚠️ RTMPose 추론 아직 미구현")
        return nil
    }

    // MARK: - 이미지 전처리
    private func preprocessImage(_ image: UIImage, targetSize: CGSize) -> [Float]? {
        // TODO: Metal로 GPU 가속 전처리
        return nil
    }
}
