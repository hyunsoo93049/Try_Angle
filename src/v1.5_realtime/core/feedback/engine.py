"""
TryAngle v1.5 - Feedback Engine

피드백 룰 오케스트레이터
"""

from typing import List
from .base_rule import FeedbackRule
from .rules.aspect_ratio_rule import AspectRatioRule
from .rules.position_rule import PositionRule
from .rules.compression_rule import CompressionRule
from ..models import FeedbackAction


class FeedbackEngine:
    """
    피드백 엔진

    모든 룰을 등록하고 실행하여 피드백 액션을 생성

    Usage:
        from infrastructure.config_manager import ConfigManager

        config = ConfigManager()
        engine = FeedbackEngine(config)

        actions = engine.generate_feedback(current_analysis, reference_analysis)
        for action in actions:
            print(action.action, action.amount)
    """

    def __init__(self, config_manager=None):
        """
        Args:
            config_manager: ConfigManager 인스턴스 (옵션)
        """
        self.config = config_manager
        self.rules: List[FeedbackRule] = []
        self._register_rules()

    def _register_rules(self):
        """
        룰 등록

        새로운 룰을 추가하려면:
        1. rules/ 디렉토리에 새 룰 클래스 생성
        2. 여기에 import 및 등록
        """
        self.rules = [
            AspectRatioRule(self.config),
            PositionRule(self.config),
            CompressionRule(self.config),
        ]

        # 우선순위로 정렬
        self.rules.sort(key=lambda r: r.priority)

        print(f"[FeedbackEngine] {len(self.rules)}개 룰 등록됨")

    def generate_feedback(self, current, reference, max_actions: int = 3) -> List[FeedbackAction]:
        """
        피드백 생성

        Args:
            current: 현재 이미지 분석 결과 (ImageAnalysis)
            reference: 레퍼런스 이미지 분석 결과 (ImageAnalysis)
            max_actions: 최대 반환 액션 개수 (기본: 3)

        Returns:
            List[FeedbackAction]: 우선순위별 피드백 액션 리스트
        """
        actions = []

        # 모든 룰 실행
        for rule in self.rules:
            action = rule.evaluate(current, reference)
            if action:
                actions.append(action)

        # 우선순위로 재정렬 (이미 정렬되어 있지만 안전장치)
        actions.sort(key=lambda a: a.priority)

        # 상위 N개만 반환
        return actions[:max_actions]

    def add_rule(self, rule: FeedbackRule):
        """
        동적으로 룰 추가

        Args:
            rule: FeedbackRule 인스턴스
        """
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
        print(f"[FeedbackEngine] 룰 추가: {rule.rule_type} (우선순위: {rule.priority})")

    def remove_rule(self, rule_type: str):
        """
        룰 제거

        Args:
            rule_type: 제거할 룰 타입
        """
        self.rules = [r for r in self.rules if r.rule_type != rule_type]
        print(f"[FeedbackEngine] 룰 제거: {rule_type}")

    def get_rules(self) -> List[FeedbackRule]:
        """등록된 모든 룰 반환"""
        return self.rules.copy()

    def get_rule_types(self) -> List[str]:
        """등록된 룰 타입 리스트 반환"""
        return [rule.rule_type for rule in self.rules]
