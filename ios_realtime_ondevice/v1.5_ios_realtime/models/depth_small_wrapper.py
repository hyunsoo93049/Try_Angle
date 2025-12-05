"""
Depth Anything Small - 경량 깊이 추정 모델 래퍼
작성일: 2025-12-05
iOS 실시간 처리용 최적화 버전
"""

import torch
import numpy as np
from PIL import Image
from typing import Optional, Dict, Any, Tuple
import cv2
import time


class DepthAnythingSmall:
    """
    Depth Anything Small 모델 래퍼

    특징:
    - 모델 크기: ~24MB
    - 처리 시간: 30-50ms (목표)
    - 정확도: MiDaS보다 좋음
    """

    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        """
        초기화

        Args:
            model_path: 모델 파일 경로
            device: 'cpu' or 'cuda'
        """
        self.device = device
        self.model = None
        self.transform = None
        self.model_loaded = False

        # 모델 설정
        self.model_config = {
            'model_type': 'small',
            'input_size': (518, 518),  # Depth Anything 기본 입력 크기
            'normalize_mean': [0.485, 0.456, 0.406],
            'normalize_std': [0.229, 0.224, 0.225]
        }

        # 성능 통계
        self.stats = {
            'total_frames': 0,
            'total_time': 0,
            'avg_time': 0
        }

    def load_model(self):
        """모델 로드 (지연 로딩)"""
        if self.model_loaded:
            return True

        try:
            # 방법 1: depth_anything 패키지 사용 (권장)
            try:
                from depth_anything.dpt import DepthAnything
                from depth_anything.util.transform import Resize, NormalizeImage, PrepareForNet
                from torchvision.transforms import Compose

                # Small 모델 로드
                self.model = DepthAnything.from_pretrained('LiheYoung/depth_anything_vits14')
                self.model = self.model.to(self.device).eval()

                # 변환 파이프라인
                self.transform = Compose([
                    Resize(
                        width=self.model_config['input_size'][0],
                        height=self.model_config['input_size'][1],
                        resize_target=False,
                        keep_aspect_ratio=True,
                        ensure_multiple_of=14,
                        resize_method='minimal',
                        image_interpolation_method=cv2.INTER_CUBIC,
                    ),
                    NormalizeImage(
                        mean=self.model_config['normalize_mean'],
                        std=self.model_config['normalize_std']
                    ),
                    PrepareForNet(),
                ])

                self.model_loaded = True
                print("[DepthSmall] depth_anything 패키지로 모델 로드 성공")
                return True

            except ImportError:
                print("[DepthSmall] depth_anything 패키지 없음, 대체 방법 시도")

            # 방법 2: transformers 사용 (대체)
            try:
                from transformers import pipeline

                self.model = pipeline(
                    'depth-estimation',
                    model='LiheYoung/depth-anything-small-hf',
                    device=0 if self.device == 'cuda' else -1
                )

                self.model_loaded = True
                print("[DepthSmall] transformers로 모델 로드 성공")
                return True

            except Exception as e:
                print(f"[DepthSmall] transformers 로드 실패: {e}")

            # 방법 3: 더미 모드 (테스트용)
            print("[DepthSmall] 경고: 더미 모드로 실행 (실제 depth 없음)")
            self.model = None
            self.model_loaded = True
            return True

        except Exception as e:
            print(f"[DepthSmall] 모델 로드 실패: {e}")
            return False

    def process_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        프레임에서 depth map 추출

        Args:
            frame: 입력 프레임 (H, W, C) BGR 형식

        Returns:
            depth_map: (H, W) normalized [0, 1] or None
        """
        if not self.model_loaded:
            if not self.load_model():
                return None

        start_time = time.perf_counter()

        try:
            # 더미 모드
            if self.model is None:
                # 간단한 gradient depth 생성 (테스트용)
                h, w = frame.shape[:2]
                depth = np.zeros((h, w), dtype=np.float32)
                # 중앙이 가깝고 가장자리가 먼 패턴
                center_x, center_y = w // 2, h // 2
                for y in range(h):
                    for x in range(w):
                        dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                        depth[y, x] = dist / (np.sqrt(center_x**2 + center_y**2))

                self._update_stats(time.perf_counter() - start_time)
                return depth

            # depth_anything 패키지 사용
            if hasattr(self, 'transform') and self.transform is not None:
                # BGR to RGB
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(image)

                # 전처리
                image_tensor = self.transform({'image': np.array(image)})['image']
                image_tensor = torch.from_numpy(image_tensor).unsqueeze(0).to(self.device)

                # 추론
                with torch.no_grad():
                    depth = self.model(image_tensor)

                # 후처리
                depth = depth.squeeze().cpu().numpy()

                # 원본 크기로 리사이즈
                depth = cv2.resize(depth, (frame.shape[1], frame.shape[0]))

                # 정규화 [0, 1]
                depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)

            # transformers pipeline 사용
            elif hasattr(self.model, '__call__'):
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(image)

                result = self.model(image)
                depth = np.array(result['depth'])

                # 정규화
                depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)

            else:
                return None

            self._update_stats(time.perf_counter() - start_time)
            return depth

        except Exception as e:
            print(f"[DepthSmall] 처리 오류: {e}")
            return None

    def calculate_compression(self, depth_map: np.ndarray,
                            person_bbox: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        압축감 지수 계산

        Args:
            depth_map: 깊이 맵
            person_bbox: 인물 영역 (x1, y1, x2, y2)

        Returns:
            압축감 정보 딕셔너리
        """
        if depth_map is None:
            return {'compression_index': 0.5, 'camera_type': 'unknown'}

        h, w = depth_map.shape

        # 전경/배경 깊이 계산
        background_region = depth_map[:h//3, :]  # 상단 1/3
        foreground_region = depth_map[3*h//4:, :]  # 하단 1/4

        bg_depth = np.mean(background_region)
        fg_depth = np.mean(foreground_region)

        # 인물 영역 깊이
        if person_bbox:
            x1, y1, x2, y2 = person_bbox
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)
            person_region = depth_map[y1:y2, x1:x2]
            person_depth = np.mean(person_region) if person_region.size > 0 else 0.5
        else:
            # 중앙 영역 사용
            center_region = depth_map[h//4:3*h//4, w//4:3*w//4]
            person_depth = np.mean(center_region)

        # 압축감 지수 계산 (0=광각, 1=망원)
        depth_range = abs(bg_depth - fg_depth)
        compression_index = 1.0 - min(depth_range * 2, 1.0)  # 범위가 작을수록 압축

        # 카메라 타입 판정
        if compression_index < 0.3:
            camera_type = "wide"  # 광각
        elif compression_index < 0.5:
            camera_type = "normal"  # 표준
        elif compression_index < 0.7:
            camera_type = "semi_tele"  # 준망원
        else:
            camera_type = "telephoto"  # 망원

        return {
            'compression_index': float(compression_index),
            'camera_type': camera_type,
            'person_depth': float(person_depth),
            'background_depth': float(bg_depth),
            'foreground_depth': float(fg_depth),
            'depth_range': float(depth_range)
        }

    def _update_stats(self, process_time: float):
        """통계 업데이트"""
        self.stats['total_frames'] += 1
        self.stats['total_time'] += process_time
        self.stats['avg_time'] = self.stats['total_time'] / self.stats['total_frames']

    def get_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        return {
            'total_frames': self.stats['total_frames'],
            'avg_time_ms': self.stats['avg_time'] * 1000,
            'model_loaded': self.model_loaded,
            'device': self.device
        }

    def warmup(self, dummy_frame: Optional[np.ndarray] = None):
        """
        모델 워밍업 (첫 추론 지연 방지)
        """
        if dummy_frame is None:
            dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        print("[DepthSmall] 워밍업 중...")
        for _ in range(3):
            _ = self.process_frame(dummy_frame)
        print(f"[DepthSmall] 워밍업 완료 (평균: {self.stats['avg_time']*1000:.1f}ms)")


# 간단한 테스트
if __name__ == "__main__":
    depth_estimator = DepthAnythingSmall(device='cpu')

    # 더미 프레임 테스트
    dummy = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # 워밍업
    depth_estimator.warmup(dummy)

    # 실제 테스트
    depth_map = depth_estimator.process_frame(dummy)

    if depth_map is not None:
        print(f"Depth map shape: {depth_map.shape}")
        print(f"Depth range: [{depth_map.min():.3f}, {depth_map.max():.3f}]")

        # 압축감 계산
        compression = depth_estimator.calculate_compression(depth_map)
        print(f"압축감: {compression['compression_index']:.2f}")
        print(f"카메라 타입: {compression['camera_type']}")
        print(f"성능: {depth_estimator.get_stats()}")
    else:
        print("Depth 추정 실패")