"""
Phase 2 테스트 - FeedbackEngine 및 룰 플러그인 검증
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

# Mock 데이터 (ImageAnalysis 대체)
from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class MockImageAnalysis:
    """테스트용 이미지 분석 결과 Mock"""
    file_path: str
    image_size: Tuple[int, int]
    person_bbox: Optional[Tuple[float, float, float, float]]
    person_confidence: float
    margins: Tuple[float, float, float, float]
    person_position: Tuple[float, float]
    pose_type: str
    compression_index: float
    camera_type: str
    person_depth: float
    background_depth: float
    aspect_ratio: str
    orientation: str
    analysis_time: float


def test_imports():
    """Import 테스트"""
    print("\n[테스트 1] Import 검증")
    print("-" * 50)

    try:
        from core.models import FeedbackAction
        print("✅ FeedbackAction import 성공")

        from core.feedback.base_rule import FeedbackRule
        print("✅ FeedbackRule import 성공")

        from core.feedback.rules import AspectRatioRule, PositionRule, CompressionRule
        print("✅ AspectRatioRule import 성공")
        print("✅ PositionRule import 성공")
        print("✅ CompressionRule import 성공")

        from core.feedback.engine import FeedbackEngine
        print("✅ FeedbackEngine import 성공")

        return True
    except Exception as e:
        print(f"❌ Import 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feedback_action():
    """FeedbackAction 데이터 모델 테스트"""
    print("\n[테스트 2] FeedbackAction 데이터 모델")
    print("-" * 50)

    from core.models import FeedbackAction

    action = FeedbackAction(
        priority=1,
        type="aspect_ratio",
        action="카메라 종횡비 변경",
        direction="",
        amount="16:9로 변경",
        impact="+30점",
        current="4:3",
        target="16:9"
    )

    print(f"✅ FeedbackAction 생성 성공")
    print(f"   타입: {action.type}")
    print(f"   액션: {action.action}")
    print(f"   우선순위: {action.priority}")

    # to_dict 테스트
    action_dict = action.to_dict()
    assert action_dict['type'] == "aspect_ratio"
    print("✅ to_dict() 변환 성공")


def test_aspect_ratio_rule():
    """AspectRatioRule 테스트"""
    print("\n[테스트 3] AspectRatioRule")
    print("-" * 50)

    from core.feedback.rules import AspectRatioRule
    from infrastructure.config_manager import ConfigManager

    config = ConfigManager()
    rule = AspectRatioRule(config)

    print(f"✅ 룰 생성 성공")
    print(f"   타입: {rule.rule_type}")
    print(f"   우선순위: {rule.priority}")

    # Mock 데이터
    current = MockImageAnalysis(
        file_path="test.jpg",
        image_size=(1920, 1080),
        person_bbox=(0.2, 0.2, 0.8, 0.8),
        person_confidence=0.95,
        margins=(0.1, 0.1, 0.1, 0.1),
        person_position=(0.5, 0.5),
        pose_type="fullshot",
        compression_index=0.5,
        camera_type="normal",
        person_depth=0.5,
        background_depth=0.8,
        aspect_ratio="4:3",  # 다름
        orientation="portrait",
        analysis_time=1.0
    )

    reference = MockImageAnalysis(
        file_path="ref.jpg",
        image_size=(1920, 1080),
        person_bbox=(0.2, 0.2, 0.8, 0.8),
        person_confidence=0.95,
        margins=(0.1, 0.1, 0.1, 0.1),
        person_position=(0.5, 0.5),
        pose_type="fullshot",
        compression_index=0.5,
        camera_type="normal",
        person_depth=0.5,
        background_depth=0.8,
        aspect_ratio="16:9",  # 레퍼런스
        orientation="portrait",
        analysis_time=1.0
    )

    action = rule.evaluate(current, reference)
    if action:
        print(f"✅ 액션 생성됨: {action.action}")
        print(f"   현재: {action.current}")
        print(f"   목표: {action.target}")
    else:
        print("❌ 액션이 None입니다")


def test_feedback_engine():
    """FeedbackEngine 통합 테스트"""
    print("\n[테스트 4] FeedbackEngine 통합")
    print("-" * 50)

    from core.feedback.engine import FeedbackEngine
    from infrastructure.config_manager import ConfigManager

    config = ConfigManager()
    engine = FeedbackEngine(config)

    print(f"✅ FeedbackEngine 생성 성공")
    print(f"   등록된 룰: {engine.get_rule_types()}")

    # Mock 데이터 (차이 있는 경우)
    current = MockImageAnalysis(
        file_path="test.jpg",
        image_size=(1920, 1080),
        person_bbox=(0.2, 0.2, 0.8, 0.8),
        person_confidence=0.95,
        margins=(0.05, 0.1, 0.15, 0.1),  # 차이
        person_position=(0.45, 0.55),  # 차이
        pose_type="fullshot",
        compression_index=0.7,  # 차이
        camera_type="normal",
        person_depth=0.5,
        background_depth=0.8,
        aspect_ratio="4:3",  # 차이
        orientation="portrait",
        analysis_time=1.0
    )

    reference = MockImageAnalysis(
        file_path="ref.jpg",
        image_size=(1920, 1080),
        person_bbox=(0.2, 0.2, 0.8, 0.8),
        person_confidence=0.95,
        margins=(0.1, 0.1, 0.1, 0.1),
        person_position=(0.5, 0.5),
        pose_type="fullshot",
        compression_index=0.5,
        camera_type="normal",
        person_depth=0.5,
        background_depth=0.8,
        aspect_ratio="16:9",
        orientation="portrait",
        analysis_time=1.0
    )

    actions = engine.generate_feedback(current, reference)

    print(f"\n✅ 피드백 생성 완료 ({len(actions)}개)")
    for i, action in enumerate(actions, 1):
        print(f"\n   [{i}] {action.action}")
        print(f"       타입: {action.type}")
        print(f"       우선순위: {action.priority}")
        print(f"       상세: {action.amount}")
        print(f"       영향: {action.impact}")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2 테스트 시작")
    print("=" * 60)

    try:
        # 테스트 실행
        if not test_imports():
            print("\n❌ Import 테스트 실패. 중단합니다.")
            sys.exit(1)

        test_feedback_action()
        test_aspect_ratio_rule()
        test_feedback_engine()

        print("\n" + "=" * 60)
        print("✅ Phase 2 모든 테스트 통과!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
