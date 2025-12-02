"""
빠른 import 테스트 (모델 로드 없음)
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

try:
    from infrastructure.model_manager import ModelManager
    print("✅ ModelManager import 성공")

    manager = ModelManager.get_instance()
    print("✅ 싱글톤 인스턴스 생성 성공")
    print(f"   Device: {manager.get_device()}")
    print(f"   로드된 모델: {manager.get_loaded_models()}")

    print("\n✅ 모든 import 테스트 통과!")
except Exception as e:
    print(f"❌ 오류: {e}")
    import traceback
    traceback.print_exc()
