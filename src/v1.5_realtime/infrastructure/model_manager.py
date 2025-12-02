"""
TryAngle v1.5 - Model Manager (Singleton Pattern)

모델 로딩 최적화를 위한 싱글톤 매니저
- 모델 한 번만 로드 (지연 로딩)
- 전역 캐싱으로 메모리 효율
- GPU 메모리 관리
"""

import torch
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# 모델 경로 추가
sys.path.append(str(Path(__file__).parent.parent.parent / "v1.5_learning"))
sys.path.append(str(Path(__file__).parent.parent.parent / "v1.5_learning" / "models"))

# 모델 wrapper import
from models.grounding_dino import GroundingDINOWrapper
from models.depth_anything import DepthAnythingWrapper


class ModelManager:
    """
    모델 관리 싱글톤 클래스

    Usage:
        manager = ModelManager.get_instance()
        grounding_dino = manager.get_model('grounding_dino')
        depth_model = manager.get_model('depth_anything')
    """

    _instance: Optional['ModelManager'] = None
    _models: Dict[str, Any] = {}
    _device: str = "cuda" if torch.cuda.is_available() else "cpu"

    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print("[ModelManager] 싱글톤 인스턴스 생성")
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'ModelManager':
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_model(self, model_name: str) -> Any:
        """
        모델 가져오기 (지연 로딩 + 캐싱)

        Args:
            model_name: 'grounding_dino' or 'depth_anything'

        Returns:
            모델 wrapper 인스턴스
        """
        # 캐시에 있으면 반환
        if model_name in self._models:
            return self._models[model_name]

        # 없으면 로드
        print(f"[ModelManager] {model_name} 모델 로딩 중...")
        model = self._load_model(model_name)
        self._models[model_name] = model
        print(f"[ModelManager] {model_name} 모델 로딩 완료 (캐시됨)")

        return model

    def _load_model(self, model_name: str) -> Any:
        """실제 모델 로딩"""
        if model_name == 'grounding_dino':
            return GroundingDINOWrapper(device=self._device)
        elif model_name == 'depth_anything':
            return DepthAnythingWrapper(device=self._device)
        else:
            raise ValueError(f"Unknown model: {model_name}")

    def is_loaded(self, model_name: str) -> bool:
        """모델이 로드되어 있는지 확인"""
        return model_name in self._models

    def cleanup(self, model_name: Optional[str] = None):
        """
        모델 메모리 정리

        Args:
            model_name: 특정 모델만 정리. None이면 전체 정리
        """
        if model_name:
            if model_name in self._models:
                del self._models[model_name]
                print(f"[ModelManager] {model_name} 모델 정리됨")
        else:
            self._models.clear()
            print("[ModelManager] 모든 모델 정리됨")

        # GPU 캐시 정리
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("[ModelManager] GPU 캐시 정리됨")

    def get_device(self) -> str:
        """현재 디바이스 반환"""
        return self._device

    def get_loaded_models(self) -> list:
        """로드된 모델 리스트 반환"""
        return list(self._models.keys())

    @classmethod
    def reset(cls):
        """싱글톤 리셋 (테스트용)"""
        if cls._instance:
            cls._instance.cleanup()
            cls._instance = None
