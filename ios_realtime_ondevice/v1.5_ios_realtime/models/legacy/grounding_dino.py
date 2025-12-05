"""
Grounding DINO 더미 래퍼 (레퍼런스 분석용)
작성일: 2025-12-05
실제 모델은 레퍼런스 분석에서만 사용, 여기서는 더미 구현
"""

import numpy as np
from typing import Optional, Dict, Any, List, Tuple


class GroundingDINOWrapper:
    """Grounding DINO 더미 래퍼 (테스트용)"""

    def __init__(self):
        self.model_loaded = False

    def load_model(self):
        """더미 모델 로드"""
        self.model_loaded = True
        return True

    def detect(self, image: np.ndarray, text_prompt: str = "person") -> List[Dict[str, Any]]:
        """더미 검출 결과 반환"""
        h, w = image.shape[:2]

        # 중앙에 더미 bbox 생성
        dummy_bbox = {
            'bbox': [w//4, h//4, 3*w//4, 3*h//4],
            'confidence': 0.95,
            'label': 'person'
        }

        return [dummy_bbox]

    def get_person_bbox(self, image: np.ndarray) -> Optional[List[int]]:
        """인물 바운딩 박스 반환"""
        detections = self.detect(image, "person")
        if detections:
            return detections[0]['bbox']
        return None