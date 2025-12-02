"""
TryAngle v1.5 - Aspect Ratio Rule

종횡비 체크 룰
"""

from typing import Optional
from ..base_rule import FeedbackRule
from ...models import FeedbackAction


class AspectRatioRule(FeedbackRule):
    """
    종횡비 룰

    레퍼런스와 현재 이미지의 종횡비가 다르면 변경 권장
    우선순위가 가장 높음 (필수 조건)
    """

    @property
    def priority(self) -> int:
        """우선순위 1 (가장 높음)"""
        return self._get_config("priority", 1)

    @property
    def rule_type(self) -> str:
        """룰 타입"""
        return "aspect_ratio"

    def evaluate(self, current, reference) -> Optional[FeedbackAction]:
        """
        종횡비 평가

        Args:
            current: 현재 이미지 분석 결과
            reference: 레퍼런스 이미지 분석 결과

        Returns:
            FeedbackAction or None: 종횡비가 다르면 액션 반환
        """
        # 종횡비가 같으면 None
        if current.aspect_ratio == reference.aspect_ratio:
            return None

        # 종횡비가 다르면 변경 권장
        impact_score = self._get_config("impact_score", 30)

        action = FeedbackAction(
            priority=self.priority,
            type=self.rule_type,
            action=self._get_message("feedback.aspect_ratio.change"),
            direction="",
            amount=f"{reference.aspect_ratio}로 변경",
            impact=f"+{impact_score}점 (필수 조건)",
            current=current.aspect_ratio,
            target=reference.aspect_ratio
        )

        return action
