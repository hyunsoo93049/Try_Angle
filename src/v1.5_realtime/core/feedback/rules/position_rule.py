"""
TryAngle v1.5 - Position Rule

위치 조정 룰 (통합 방향 계산)
"""

from typing import Optional
from ..base_rule import FeedbackRule
from ...models import FeedbackAction


class PositionRule(FeedbackRule):
    """
    위치 조정 룰

    레퍼런스와 현재 이미지의 피사체 위치를 비교하여
    카메라 이동 방향을 제안
    """

    @property
    def priority(self) -> int:
        """우선순위 2"""
        return self._get_config("priority", 2)

    @property
    def rule_type(self) -> str:
        """룰 타입"""
        return "position"

    def evaluate(self, current, reference) -> Optional[FeedbackAction]:
        """
        위치 평가

        Args:
            current: 현재 이미지 분석 결과
            reference: 레퍼런스 이미지 분석 결과

        Returns:
            FeedbackAction or None: 위치 차이가 크면 액션 반환
        """
        # 마진 차이 계산
        margin_diffs = {
            'top': current.margins[0] - reference.margins[0],
            'right': current.margins[1] - reference.margins[1],
            'bottom': current.margins[2] - reference.margins[2],
            'left': current.margins[3] - reference.margins[3]
        }

        # 포지션 차이 계산
        position_diff = (
            current.person_position[0] - reference.person_position[0],
            current.person_position[1] - reference.person_position[1]
        )

        # 통합 방향 계산
        h_move, v_move = self._calculate_unified_direction(margin_diffs, position_diff)

        # 임계값 확인
        threshold = self._get_config("threshold", 0.03)
        if abs(h_move) < threshold and abs(v_move) < threshold:
            return None

        # 방향 및 액션 결정
        direction_str, direction_arrow, amount = self._determine_direction(h_move, v_move)

        # 영향 점수 계산
        impact_score = self._get_config("impact_score", 10)
        max_move = max(abs(h_move), abs(v_move))

        action = FeedbackAction(
            priority=self.priority,
            type=self.rule_type,
            action=f"카메라 {direction_str} 이동",
            direction=direction_arrow,
            amount=amount,
            impact=f"+{max_move * impact_score * 5:.0f}점"
        )

        return action

    def _calculate_unified_direction(self, margin_diffs, position_diff):
        """마진과 포지션을 통합한 방향 계산"""
        # 수평 방향 통합
        horizontal = 0
        if abs(position_diff[0]) > 0.03:  # position이 더 중요
            horizontal = -position_diff[0]
        elif abs(margin_diffs['left'] - margin_diffs['right']) > 0.05:
            horizontal = (margin_diffs['left'] - margin_diffs['right']) / 2

        # 수직 방향 통합
        vertical = 0
        if abs(position_diff[1]) > 0.03:  # position이 더 중요
            vertical = -position_diff[1]
        elif abs(margin_diffs['top'] - margin_diffs['bottom']) > 0.05:
            vertical = (margin_diffs['top'] - margin_diffs['bottom']) / 2

        return horizontal, vertical

    def _determine_direction(self, h_move, v_move):
        """방향 문자열과 화살표 결정"""
        direction_str = ""
        direction_arrow = ""
        amount = ""

        # 대각선 이동이 필요한 경우
        if abs(h_move) > 0.03 and abs(v_move) > 0.03:
            if h_move > 0 and v_move > 0:
                direction_str = "오른쪽 위로"
                direction_arrow = "↗"
            elif h_move > 0 and v_move < 0:
                direction_str = "오른쪽 아래로"
                direction_arrow = "↘"
            elif h_move < 0 and v_move > 0:
                direction_str = "왼쪽 위로"
                direction_arrow = "↖"
            else:
                direction_str = "왼쪽 아래로"
                direction_arrow = "↙"
            amount = f"가로 {abs(h_move)*100:.0f}%, 세로 {abs(v_move)*100:.0f}%"

        # 주로 수직 이동
        elif abs(v_move) > abs(h_move):
            if v_move > 0:
                direction_str = "위로"
                direction_arrow = "↑"
            else:
                direction_str = "아래로"
                direction_arrow = "↓"
            amount = f"{abs(v_move)*100:.0f}%"

        # 주로 수평 이동
        else:
            if h_move > 0:
                direction_str = "오른쪽으로"
                direction_arrow = "→"
            else:
                direction_str = "왼쪽으로"
                direction_arrow = "←"
            amount = f"{abs(h_move)*100:.0f}%"

        return direction_str, direction_arrow, amount
