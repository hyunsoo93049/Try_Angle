"""
TryAngle v1.5 - FeedbackRule Base Class

피드백 룰 베이스 클래스 (플러그인 아키텍처)
"""

from abc import ABC, abstractmethod
from typing import Optional
from ..models import FeedbackAction


class FeedbackRule(ABC):
    """
    피드백 룰 베이스 클래스

    모든 피드백 룰은 이 클래스를 상속받아 구현
    새로운 룰 추가 시 이 클래스를 상속받아 구현하면 됨
    """

    def __init__(self, config_manager=None):
        """
        Args:
            config_manager: ConfigManager 인스턴스 (룰 설정 로드용)
        """
        self.config = config_manager

    @property
    @abstractmethod
    def priority(self) -> int:
        """
        룰의 기본 우선순위 (낮을수록 먼저 실행)

        Returns:
            int: 우선순위 숫자
        """
        pass

    @property
    @abstractmethod
    def rule_type(self) -> str:
        """
        룰 타입

        Returns:
            str: 룰 타입 (aspect_ratio, position, compression, margin)
        """
        pass

    @abstractmethod
    def evaluate(self, current, reference) -> Optional[FeedbackAction]:
        """
        룰 평가

        Args:
            current: 현재 이미지 분석 결과 (ImageAnalysis)
            reference: 레퍼런스 이미지 분석 결과 (ImageAnalysis)

        Returns:
            FeedbackAction or None: 피드백 액션 (룰이 적용되지 않으면 None)
        """
        pass

    def _get_config(self, key: str, default=None):
        """
        설정값 가져오기

        Args:
            key: 설정 키
            default: 기본값

        Returns:
            설정값 또는 기본값
        """
        if self.config is None:
            return default

        return self.config.get_rule(self.rule_type, key) or default

    def _get_message(self, message_key: str, **kwargs) -> str:
        """
        메시지 가져오기

        Args:
            message_key: 메시지 키
            **kwargs: 템플릿 변수

        Returns:
            포맷팅된 메시지
        """
        if self.config is None:
            return message_key

        return self.config.get_message(message_key, **kwargs)
