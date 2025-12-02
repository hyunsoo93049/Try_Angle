"""
ModelManager 검증 테스트
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from infrastructure.model_manager import ModelManager
import time


def test_singleton_pattern():
    """싱글톤 패턴 검증"""
    print("\n[테스트 1] 싱글톤 패턴 검증")
    print("-" * 50)

    manager1 = ModelManager.get_instance()
    manager2 = ModelManager.get_instance()

    assert manager1 is manager2, "싱글톤 패턴 실패!"
    print("✅ 싱글톤 패턴 정상 작동")
    print(f"   manager1 id: {id(manager1)}")
    print(f"   manager2 id: {id(manager2)}")


def test_lazy_loading():
    """지연 로딩 검증"""
    print("\n[테스트 2] 지연 로딩 검증")
    print("-" * 50)

    manager = ModelManager.get_instance()

    # 초기 상태: 모델 없음
    assert not manager.is_loaded('grounding_dino'), "모델이 이미 로드됨!"
    print("✅ 초기 상태: 모델 로드 안됨")

    # 첫 번째 요청: 모델 로드 (시간 측정)
    start = time.time()
    model1 = manager.get_model('grounding_dino')
    load_time = time.time() - start
    print(f"✅ 첫 로딩 시간: {load_time:.2f}초")

    assert manager.is_loaded('grounding_dino'), "모델 로드 실패!"

    # 두 번째 요청: 캐시에서 반환 (즉시)
    start = time.time()
    model2 = manager.get_model('grounding_dino')
    cache_time = time.time() - start
    print(f"✅ 캐시 반환 시간: {cache_time:.4f}초")

    assert model1 is model2, "캐싱 실패!"
    assert cache_time < 0.01, f"캐시가 느림: {cache_time}초"


def test_multiple_models():
    """여러 모델 로딩 검증"""
    print("\n[테스트 3] 여러 모델 로딩 검증")
    print("-" * 50)

    manager = ModelManager.get_instance()

    # GroundingDINO 로드
    grounding_dino = manager.get_model('grounding_dino')
    print("✅ GroundingDINO 로드됨")

    # DepthAnything 로드
    depth_model = manager.get_model('depth_anything')
    print("✅ DepthAnything 로드됨")

    # 로드된 모델 확인
    loaded = manager.get_loaded_models()
    print(f"   로드된 모델: {loaded}")
    assert 'grounding_dino' in loaded
    assert 'depth_anything' in loaded


def test_cleanup():
    """메모리 정리 검증"""
    print("\n[테스트 4] 메모리 정리 검증")
    print("-" * 50)

    manager = ModelManager.get_instance()

    # 모델 로드
    manager.get_model('grounding_dino')
    assert manager.is_loaded('grounding_dino')

    # 특정 모델 정리
    manager.cleanup('grounding_dino')
    assert not manager.is_loaded('grounding_dino')
    print("✅ 특정 모델 정리 성공")

    # 전체 정리
    manager.get_model('depth_anything')
    manager.cleanup()
    assert len(manager.get_loaded_models()) == 0
    print("✅ 전체 모델 정리 성공")


def test_performance_comparison():
    """기존 방식 vs ModelManager 성능 비교"""
    print("\n[테스트 5] 성능 비교")
    print("-" * 50)

    # ModelManager 리셋
    ModelManager.reset()

    # 첫 번째 인스턴스 (모델 로드 시간)
    start = time.time()
    manager1 = ModelManager.get_instance()
    model1 = manager1.get_model('grounding_dino')
    first_time = time.time() - start
    print(f"첫 번째 로딩: {first_time:.2f}초")

    # 두 번째 인스턴스 (캐시 사용 시간)
    start = time.time()
    manager2 = ModelManager.get_instance()
    model2 = manager2.get_model('grounding_dino')
    second_time = time.time() - start
    print(f"두 번째 로딩: {second_time:.4f}초")

    speedup = first_time / second_time if second_time > 0 else float('inf')
    print(f"\n✅ 성능 개선: {speedup:.0f}배 빠름")
    print(f"   절약 시간: {first_time - second_time:.2f}초")


if __name__ == "__main__":
    print("=" * 60)
    print("ModelManager 검증 테스트 시작")
    print("=" * 60)

    try:
        test_singleton_pattern()
        test_lazy_loading()
        test_multiple_models()
        test_cleanup()
        test_performance_comparison()

        print("\n" + "=" * 60)
        print("✅ 모든 테스트 통과!")
        print("=" * 60)

        # 최종 상태 출력
        manager = ModelManager.get_instance()
        print(f"\n최종 상태:")
        print(f"  디바이스: {manager.get_device()}")
        print(f"  로드된 모델: {manager.get_loaded_models()}")

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
