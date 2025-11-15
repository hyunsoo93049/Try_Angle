# ============================================================
# 🚀 TryAngle - Model Cache (Singleton)
# 모델을 한 번만 로드하여 속도 개선
# ============================================================

class ModelCache:
    """
    싱글톤 패턴으로 모델 캐싱
    - YOLO, Feature Extractor, Cluster Matcher 등
    """
    _instance = None
    _models = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_or_load(self, model_name: str, loader_func):
        """
        모델이 캐시에 있으면 반환, 없으면 로드 후 캐시

        Args:
            model_name: 모델 식별자 (예: "yolo_pose", "embedder")
            loader_func: 모델 로딩 함수 (callable)

        Returns:
            로드된 모델
        """
        if model_name not in self._models:
            print(f"  🔧 Loading {model_name} (first time)...")
            self._models[model_name] = loader_func()
            print(f"  ✅ {model_name} loaded and cached")
        else:
            print(f"  ♻️ Using cached {model_name}")

        return self._models[model_name]

    def clear(self):
        """캐시 초기화 (메모리 해제)"""
        self._models.clear()
        print("  🧹 Model cache cleared")


# 전역 싱글톤 인스턴스
model_cache = ModelCache()
