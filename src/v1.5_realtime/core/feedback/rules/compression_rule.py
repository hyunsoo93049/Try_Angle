"""
TryAngle v1.5 - Compression Rule

압축감 조정 룰 (렌즈 초점거리)
"""

from typing import Optional
from ..base_rule import FeedbackRule
from ...models import FeedbackAction


class CompressionRule(FeedbackRule):
    """
    압축감 조정 룰

    레퍼런스와 현재 이미지의 압축감(compression_index)을 비교하여
    렌즈 초점거리 변경을 제안
    """

    @property
    def priority(self) -> int:
        """우선순위 3"""
        return self._get_config("priority", 3)

    @property
    def rule_type(self) -> str:
        """룰 타입"""
        return "compression"

    def evaluate(self, current, reference) -> Optional[FeedbackAction]:
        """
        압축감 평가

        Args:
            current: 현재 이미지 분석 결과
            reference: 레퍼런스 이미지 분석 결과

        Returns:
            FeedbackAction or None: 압축감 차이가 크면 액션 반환
        """
        # 압축감 차이 계산
        compression_diff = current.compression_index - reference.compression_index

        # 임계값 확인
        threshold = self._get_config("threshold", 0.1)
        if abs(compression_diff) < threshold:
            return None

        # 액션 및 상세 설명 결정
        if compression_diff > 0:
            # 현재가 더 압축됨 -> 광각으로
            action_text = "광각 렌즈로 변경"
            detail = "24-35mm 추천"
        else:
            # 현재가 덜 압축됨 -> 망원으로
            action_text = "망원 렌즈로 변경"
            detail = "85mm 이상 추천"

        # 영향 점수 계산
        impact_score = self._get_config("impact_score", 5)

        action = FeedbackAction(
            priority=self.priority,
            type=self.rule_type,
            action=action_text,
            direction="",
            amount=detail,
            impact=f"+{abs(compression_diff) * impact_score * 4:.0f}점"
        )

        return action
