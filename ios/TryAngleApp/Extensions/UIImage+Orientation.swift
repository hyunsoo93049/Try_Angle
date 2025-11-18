import UIKit

extension UIImage {
    /// 이미지 방향을 올바르게 수정
    func fixedOrientation() -> UIImage {
        // 이미 올바른 방향이면 그대로 반환
        if imageOrientation == .up {
            return self
        }

        // 방향을 고려하여 새 이미지 생성
        guard let cgImage = cgImage else { return self }

        let width = size.width
        let height = size.height

        var transform = CGAffineTransform.identity

        switch imageOrientation {
        case .down, .downMirrored:
            transform = transform.translatedBy(x: width, y: height)
            transform = transform.rotated(by: .pi)

        case .left, .leftMirrored:
            transform = transform.translatedBy(x: width, y: 0)
            transform = transform.rotated(by: .pi / 2)

        case .right, .rightMirrored:
            transform = transform.translatedBy(x: 0, y: height)
            transform = transform.rotated(by: -.pi / 2)

        default:
            break
        }

        switch imageOrientation {
        case .upMirrored, .downMirrored:
            transform = transform.translatedBy(x: width, y: 0)
            transform = transform.scaledBy(x: -1, y: 1)

        case .leftMirrored, .rightMirrored:
            transform = transform.translatedBy(x: height, y: 0)
            transform = transform.scaledBy(x: -1, y: 1)

        default:
            break
        }

        guard let context = CGContext(
            data: nil,
            width: Int(width),
            height: Int(height),
            bitsPerComponent: cgImage.bitsPerComponent,
            bytesPerRow: 0,
            space: cgImage.colorSpace!,
            bitmapInfo: cgImage.bitmapInfo.rawValue
        ) else {
            return self
        }

        context.concatenate(transform)

        switch imageOrientation {
        case .left, .leftMirrored, .right, .rightMirrored:
            context.draw(cgImage, in: CGRect(x: 0, y: 0, width: height, height: width))

        default:
            context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        }

        guard let newCGImage = context.makeImage() else {
            return self
        }

        return UIImage(cgImage: newCGImage)
    }
}
