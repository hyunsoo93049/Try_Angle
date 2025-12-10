import SwiftUI
import AVFoundation

struct CameraView: UIViewRepresentable {
    @ObservedObject var cameraManager: CameraManager

    func makeUIView(context: Context) -> UIView {
        let view = UIView(frame: .zero)
        view.backgroundColor = .black
        
        // 🆕 Preview Layer는 여기서 추가하지 않음 (updateUIView에서 조건부 추가)

        // 핀치 제스처 (줌)
        let pinchGesture = UIPinchGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handlePinch(_:)))
        view.addGestureRecognizer(pinchGesture)

        // 탭 제스처 (초점)
        let tapGesture = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handleTap(_:)))
        view.addGestureRecognizer(tapGesture)

        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        // 🆕 세션 설정이 완료된 후에만 Preview Layer 연결
        let hasPreviewLayer = uiView.layer.sublayers?.contains(where: { $0 is AVCaptureVideoPreviewLayer }) ?? false
        
        if cameraManager.isSessionConfigured && !hasPreviewLayer {
            // 처음으로 Preview Layer 추가
            let previewLayer = cameraManager.previewLayer
            previewLayer.frame = uiView.bounds
            uiView.layer.insertSublayer(previewLayer, at: 0) // 맨 뒤에 추가
            print("✅ [CameraView] Preview Layer 연결 완료 (Session Ready)")
        }
        
        // 기존 Preview Layer 프레임 업데이트 (bounds 변경 대응)
        if let previewLayer = uiView.layer.sublayers?.first(where: { $0 is AVCaptureVideoPreviewLayer }) as? AVCaptureVideoPreviewLayer {
            // 애니메이션 없이 즉시 프레임 업데이트
            CATransaction.begin()
            CATransaction.setDisableActions(true)
            previewLayer.frame = uiView.bounds
            CATransaction.commit()
            
            // 16:9(Full Screen)일 때만 Fill로 설정하여 "확대된 느낌" 구현
            if cameraManager.aspectRatio == .ratio16_9 {
                previewLayer.videoGravity = .resizeAspectFill
            } else {
                previewLayer.videoGravity = .resizeAspect
            }
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(cameraManager: cameraManager)
    }

    class Coordinator: NSObject {
        let cameraManager: CameraManager
        private var initialZoom: CGFloat = 1.0

        init(cameraManager: CameraManager) {
            self.cameraManager = cameraManager
        }

        @objc func handlePinch(_ gesture: UIPinchGestureRecognizer) {
            switch gesture.state {
            case .began:
                initialZoom = cameraManager.virtualZoom
            case .changed:
                let targetZoom = initialZoom * gesture.scale
                cameraManager.setZoomImmediate(targetZoom)
            case .ended, .cancelled:
                initialZoom = 1.0
            default:
                break
            }
        }

        @objc func handleTap(_ gesture: UITapGestureRecognizer) {
            guard let view = gesture.view else { return }
            let point = gesture.location(in: view)
            
            // 프리뷰 레이어 좌표계로 변환 (0.0 ~ 1.0)
            if let previewLayer = view.layer.sublayers?.first(where: { $0 is AVCaptureVideoPreviewLayer }) as? AVCaptureVideoPreviewLayer {
                let devicePoint = previewLayer.captureDevicePointConverted(fromLayerPoint: point)
                cameraManager.setFocus(at: devicePoint)
                print("👆 Tap to Focus: \(devicePoint)")
            }
        }
    }
}
