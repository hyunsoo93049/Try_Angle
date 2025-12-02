"""
TryAngle v1.5 - Core Data Models

핵심 데이터 모델 정의
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FeedbackAction:
    """
    피드백 액션

    각 룰이 생성하는 피드백 액션을 나타냄
    """
    # 기본 정보
    priority: int  # 우선순위 (낮을수록 먼저)
    type: str  # aspect_ratio, position, compression, margin
    action: str  # 사용자에게 보여줄 액션 메시지

    # 상세 정보
    direction: str = ""  # 방향 (↑, ↓, ←, →, ↗, ↘, ↖, ↙)
    amount: str = ""  # 변경량 또는 상세 설명
    impact: str = ""  # 예상 개선 효과 (+30점 등)

    # 추가 메타데이터
    current: Optional[str] = None  # 현재 값
    target: Optional[str] = None  # 목표 값

    def to_dict(self):
        """딕셔너리로 변환 (호환성 유지)"""
        return {
            'priority': self.priority,
            'type': self.type,
            'action': self.action,
            'direction': self.direction,
            'amount': self.amount,
            'impact': self.impact,
            'current': self.current,
            'target': self.target,
        }
