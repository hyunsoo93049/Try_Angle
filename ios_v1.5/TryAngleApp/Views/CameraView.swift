import SwiftUI
import AVFoundation

struct CameraView: UIViewRepresentable {
    let cameraManager: CameraManager

    func makeUIView(context: Context) -> UIView {
        let view = UIView(frame: .zero)
        view.backgroundColor = .black

        let previewLayer = cameraManager.previewLayer
        previewLayer.frame = view.bounds
        view.layer.addSublayer(previewLayer)

        // 핀치 제스처 (줌)
        let pinchGesture = UIPinchGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handlePinch(_:)))
        view.addGestureRecognizer(pinchGesture)

        // 탭 제스처 (초점)
        let tapGesture = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handleTap(_:)))
        view.addGestureRecognizer(tapGesture)

        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        if let previewLayer = uiView.layer.sublayers?.first as? AVCaptureVideoPreviewLayer {
            DispatchQueue.main.async {
                previewLayer.frame = uiView.bounds
                
                // 16:9(Full Screen)일 때만 Fill로 설정하여 "확대된 느낌" 구현
                if context.coordinator.cameraManager.aspectRatio == .ratio16_9 {
                    previewLayer.videoGravity = .resizeAspectFill
                } else {
                    previewLayer.videoGravity = .resizeAspect
                }
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
            if let previewLayer = view.layer.sublayers?.first as? AVCaptureVideoPreviewLayer {
                let devicePoint = previewLayer.captureDevicePointConverted(fromLayerPoint: point)
                cameraManager.setFocus(at: devicePoint)
                
                // (선택 사항) 터치 이펙트 표시 로직을 여기에 추가할 수 있음
                print("👆 Tap to Focus: \(devicePoint)")
            }
        }
    }
}
