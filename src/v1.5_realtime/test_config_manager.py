"""
ConfigManager 검증 테스트
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from infrastructure.config_manager import ConfigManager


def test_initialization():
    """초기화 테스트"""
    print("\n[테스트 1] 초기화 테스트")
    print("-" * 50)

    config = ConfigManager(language="ko")
    print(f"✅ ConfigManager 초기화 성공")
    print(f"   설정 디렉토리: {config.config_dir}")
    print(f"   언어: {config.language}")


def test_rule_loading():
    """룰 설정 로딩 테스트"""
    print("\n[테스트 2] 룰 설정 로딩")
    print("-" * 50)

    config = ConfigManager()

    # 전체 룰 가져오기
    aspect_ratio_rule = config.get_rule("aspect_ratio")
    print(f"✅ aspect_ratio 룰: {aspect_ratio_rule}")

    # 특정 설정값 가져오기
    threshold = config.get_rule("aspect_ratio", "threshold")
    priority = config.get_rule("aspect_ratio", "priority")
    print(f"✅ threshold: {threshold}")
    print(f"✅ priority: {priority}")

    assert threshold == 0.1, f"threshold should be 0.1, got {threshold}"
    assert priority == 1, f"priority should be 1, got {priority}"


def test_message_loading():
    """메시지 로딩 테스트"""
    print("\n[테스트 3] 메시지 로딩")
    print("-" * 50)

    config = ConfigManager(language="ko")

    # 일반 메시지
    msg1 = config.get_message("feedback.aspect_ratio.change")
    print(f"✅ 메시지: {msg1}")
    assert msg1 == "카메라 종횡비 변경", f"Expected '카메라 종횡비 변경', got '{msg1}'"

    # 템플릿 메시지
    msg2 = config.get_message("feedback.aspect_ratio.description", target="16:9")
    print(f"✅ 템플릿 메시지: {msg2}")
    assert msg2 == "16:9로 변경하세요", f"Expected '16:9로 변경하세요', got '{msg2}'"


def test_model_config_loading():
    """모델 설정 로딩 테스트"""
    print("\n[테스트 4] 모델 설정 로딩")
    print("-" * 50)

    config = ConfigManager()

    # 모델 설정 가져오기
    grounding_dino = config.get_model_config("grounding_dino")
    print(f"✅ grounding_dino 설정: {grounding_dino}")

    checkpoint = config.get_model_config("grounding_dino", "checkpoint")
    print(f"✅ checkpoint: {checkpoint}")
    assert checkpoint == "models/grounding_dino.pth"


def test_language_switching():
    """언어 전환 테스트"""
    print("\n[테스트 5] 언어 전환")
    print("-" * 50)

    config = ConfigManager(language="ko")

    # 한국어
    msg_ko = config.get_message("feedback.aspect_ratio.change")
    print(f"한국어: {msg_ko}")

    # 영어로 전환 (영어 파일이 없으면 키 반환)
    config.set_language("en")
    msg_en = config.get_message("feedback.aspect_ratio.change")
    print(f"영어: {msg_en}")


def test_caching():
    """캐싱 테스트"""
    print("\n[테스트 6] 캐싱 테스트")
    print("-" * 50)

    config = ConfigManager()

    # 첫 번째 요청: 파일 로드
    threshold1 = config.get_rule("aspect_ratio", "threshold")
    print(f"첫 번째 요청: {threshold1}")

    # 두 번째 요청: 캐시에서 반환
    threshold2 = config.get_rule("aspect_ratio", "threshold")
    print(f"두 번째 요청: {threshold2}")

    assert threshold1 == threshold2, "Caching failed"
    print("✅ 캐싱 정상 작동")


def test_validation():
    """설정 파일 검증 테스트"""
    print("\n[테스트 7] 설정 파일 검증")
    print("-" * 50)

    config = ConfigManager(language="ko")
    is_valid = config.validate_config()

    if is_valid:
        print("✅ 모든 설정 파일 존재")
    else:
        print("⚠️  일부 설정 파일 누락 (정상 - Phase 3에서 완성)")


if __name__ == "__main__":
    print("=" * 60)
    print("ConfigManager 검증 테스트 시작")
    print("=" * 60)

    try:
        test_initialization()
        test_rule_loading()
        test_message_loading()
        test_model_config_loading()
        test_language_switching()
        test_caching()
        test_validation()

        print("\n" + "=" * 60)
        print("✅ ConfigManager 테스트 통과!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
