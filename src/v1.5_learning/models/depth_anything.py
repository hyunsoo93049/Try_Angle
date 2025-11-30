# ============================================================
# TryAngle v1.5 - Depth Anything V2 Wrapper
# 깊이 분석 및 압축감(Compression Index) 계산
# ============================================================

import torch
import numpy as np
from PIL import Image
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class DepthAnalysisResult:
    """깊이 분석 결과"""
    depth_map: np.ndarray                    # 원본 depth map
    person_depth: float                      # 인물 평균 깊이
    background_depth: float                  # 배경 평균 깊이
    foreground_depth: float                  # 전경 평균 깊이
    compression_index: float                 # 압축감 지수 (0=광각, 1=망원)
    camera_type: str                         # 카메라 타입 추정


class DepthAnythingWrapper:
    """
    Depth Anything V2 모델 래퍼

    Usage:
        wrapper = DepthAnythingWrapper(device="cuda")
        result = wrapper.analyze(image, person_bbox=(0.2, 0.1, 0.6, 0.9))
    """

    def __init__(
        self,
        model_id: str = "depth-anything/Depth-Anything-V2-Large",
        device: str = "cuda"
    ):
        self.model_id = model_id
        self.device = device
        self.model = None
        self.transform = None

    def load(self):
        """모델 로드"""
        try:
            # 방법 1: Depth-Anything-V2 공식 repo 사용
            from depth_anything_v2.dpt import DepthAnythingV2

            model_configs = {
                'vits': {'encoder': 'vits', 'features': 64, 'out_channels': [48, 96, 192, 384]},
                'vitb': {'encoder': 'vitb', 'features': 128, 'out_channels': [96, 192, 384, 768]},
                'vitl': {'encoder': 'vitl', 'features': 256, 'out_channels': [256, 512, 1024, 1024]},
            }

            # Large 모델 사용
            self.model = DepthAnythingV2(**model_configs['vitl'])
            self.model.load_state_dict(torch.load(
                'checkpoints/depth_anything_v2_vitl.pth',
                map_location=self.device
            ))
            self.model = self.model.to(self.device).eval()
            self._use_native = True
            print(f"[DepthAnything] Loaded native V2 Large on {self.device}")

        except (ImportError, FileNotFoundError):
            # 방법 2: HuggingFace transformers 사용
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation

            self.processor = AutoImageProcessor.from_pretrained(
                "depth-anything/Depth-Anything-V2-Large-hf"
            )
            self.model = AutoModelForDepthEstimation.from_pretrained(
                "depth-anything/Depth-Anything-V2-Large-hf"
            ).to(self.device)
            self._use_native = False
            print(f"[DepthAnything] Loaded HuggingFace model on {self.device}")

    def analyze(
        self,
        image: Image.Image,
        person_bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> DepthAnalysisResult:
        """
        이미지 깊이 분석

        Args:
            image: PIL Image
            person_bbox: (x1, y1, x2, y2) normalized [0-1]

        Returns:
            DepthAnalysisResult
        """
        if self.model is None:
            self.load()

        # Depth map 생성
        if self._use_native:
            depth_map = self._predict_native(image)
        else:
            depth_map = self._predict_hf(image)

        # 분석 수행
        h, w = depth_map.shape
        width, height = image.size

        # 배경 깊이 (상단 1/3)
        background_region = depth_map[:h//3, :]
        background_depth = float(np.mean(background_region))

        # 전경 깊이 (하단 1/4)
        foreground_region = depth_map[3*h//4:, :]
        foreground_depth = float(np.mean(foreground_region))

        # 인물 깊이
        if person_bbox:
            x1, y1, x2, y2 = person_bbox
            px1 = int(x1 * w)
            py1 = int(y1 * h)
            px2 = int(x2 * w)
            py2 = int(y2 * h)
            person_region = depth_map[py1:py2, px1:px2]
            person_depth = float(np.mean(person_region)) if person_region.size > 0 else 128.0
        else:
            # bbox 없으면 중앙 영역 사용
            center_region = depth_map[h//4:3*h//4, w//4:3*w//4]
            person_depth = float(np.mean(center_region))

        # Compression Index 계산
        total_range = abs(background_depth - foreground_depth)
        max_possible_range = 255.0

        # 압축감: 범위가 작을수록 망원 (압축됨)
        compression_index = 1.0 - (total_range / max_possible_range)
        compression_index = max(0.0, min(1.0, compression_index))

        # 카메라 타입 추정
        if compression_index < 0.3:
            camera_type = "wide_angle"        # 광각 (24mm 이하)
        elif compression_index < 0.5:
            camera_type = "normal"            # 표준 (35-50mm)
        elif compression_index < 0.7:
            camera_type = "normal_to_tele"    # 준망원 (50-85mm)
        else:
            camera_type = "telephoto"         # 망원 (85mm 이상)

        return DepthAnalysisResult(
            depth_map=depth_map,
            person_depth=person_depth,
            background_depth=background_depth,
            foreground_depth=foreground_depth,
            compression_index=compression_index,
            camera_type=camera_type
        )

    def _predict_native(self, image: Image.Image) -> np.ndarray:
        """Native Depth Anything V2 사용"""
        import cv2

        # PIL to numpy
        img_np = np.array(image)

        # Grayscale/RGBA 처리
        if len(img_np.shape) == 2:  # Grayscale
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif img_np.shape[2] == 4:  # RGBA
            img_np = img_np[:, :, :3]

        # BGR로 변환 (OpenCV 형식)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        with torch.no_grad():
            depth = self.model.infer_image(img_bgr)

        # Normalize to 0-255
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8) * 255
        return depth.astype(np.uint8)

    def _predict_hf(self, image: Image.Image) -> np.ndarray:
        """HuggingFace transformers 사용"""
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            predicted_depth = outputs.predicted_depth

        # Interpolate to original size
        prediction = torch.nn.functional.interpolate(
            predicted_depth.unsqueeze(1),
            size=image.size[::-1],  # (height, width)
            mode="bicubic",
            align_corners=False,
        )

        depth = prediction.squeeze().cpu().numpy()

        # Normalize to 0-255
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8) * 255
        return depth.astype(np.uint8)


# ============================================================
# Quick Test
# ============================================================
if __name__ == "__main__":
    from PIL import Image

    wrapper = DepthAnythingWrapper(device="cuda")

    # 테스트 이미지
    test_image = Image.new("RGB", (640, 480), color="gray")

    result = wrapper.analyze(
        test_image,
        person_bbox=(0.3, 0.1, 0.7, 0.9)
    )

    print(f"Compression Index: {result.compression_index:.3f}")
    print(f"Camera Type: {result.camera_type}")
    print(f"Person Depth: {result.person_depth:.1f}")
    print(f"Background Depth: {result.background_depth:.1f}")
