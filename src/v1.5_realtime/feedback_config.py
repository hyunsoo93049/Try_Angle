#!/usr/bin/env python3
"""
Feedback Messages Configuration Manager
YAML 기반 다국어 피드백 메시지 관리
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class FeedbackConfig:
    """YAML 기반 피드백 메시지 관리자"""

    def __init__(self, config_path: Optional[str] = None, language: str = 'ko'):
        """
        초기화

        Args:
            config_path: YAML 설정 파일 경로
            language: 사용할 언어 ('ko', 'en')
        """
        if config_path is None:
            config_path = Path(__file__).parent / "feedback_messages.yaml"

        self.config_path = Path(config_path)
        self.language = language
        self.messages = {}

        # YAML 파일 로드
        self._load_config()

    def _load_config(self):
        """YAML 설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
                self.messages = self.config.get('messages', {})

            # 기본 언어 설정
            if not self.language:
                self.language = self.config.get('default_language', 'ko')

            print(f"[FeedbackConfig] 언어 설정: {self.language}")

        except FileNotFoundError:
            print(f"[FeedbackConfig] 설정 파일 없음: {self.config_path}")
            self._use_default_messages()
        except Exception as e:
            print(f"[FeedbackConfig] 설정 로드 실패: {e}")
            self._use_default_messages()

    def _use_default_messages(self):
        """기본 메시지 사용 (파일 로드 실패시)"""
        self.messages = {
            'headers': {
                'main_title': {'ko': '[TryAngle v1.5] 분석', 'en': '[TryAngle v1.5] Analysis'}
            }
        }

    def get(self, key_path: str, default: str = '', **kwargs) -> str:
        """
        메시지 가져오기

        Args:
            key_path: 점으로 구분된 키 경로 (예: 'headers.main_title')
            default: 키가 없을 때 기본값
            **kwargs: 문자열 포맷팅 인자

        Returns:
            현재 언어의 메시지
        """
        keys = key_path.split('.')
        value = self.messages

        # 키 경로 따라가기
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        # 언어별 메시지 선택
        if isinstance(value, dict):
            message = value.get(self.language, value.get('ko', default))
        else:
            message = value

        # 포맷팅 적용
        if kwargs and '{}' in message:
            try:
                # format 스타일 변환
                args_list = list(kwargs.values())
                message = message.format(*args_list)
            except:
                pass

        return message

    def get_shot_type(self, shot_type: str) -> Dict[str, str]:
        """샷 타입 정보 가져오기"""
        shot_info = self.messages.get('shot_types', {}).get(shot_type, {})
        return {
            'name': shot_info.get(self.language, shot_info.get('en', shot_type)),
            'description': shot_info.get('description', {}).get(self.language, '')
        }

    def get_gesture(self, gesture: str) -> str:
        """손 제스처 이름 가져오기"""
        gestures = self.messages.get('hand_gestures', {})
        gesture_info = gestures.get(gesture, gestures.get('unknown', {}))

        if isinstance(gesture_info, dict):
            return gesture_info.get(self.language, gesture)
        return gesture

    def get_impact_level(self, level: str) -> str:
        """중요도 레벨 가져오기"""
        levels = self.messages.get('impact_levels', {})
        level_info = levels.get(level, {})

        if isinstance(level_info, dict):
            return level_info.get(self.language, level)
        return level

    def switch_language(self, language: str):
        """언어 전환"""
        if language in self.config.get('languages', ['ko', 'en']):
            self.language = language
            print(f"[FeedbackConfig] 언어 전환: {language}")
        else:
            print(f"[FeedbackConfig] 지원하지 않는 언어: {language}")

    def format_adjustment_method(self, method_key: str, *args) -> str:
        """조정 방법 포맷팅"""
        methods = self.messages.get('adjustment_methods', {})
        method_template = methods.get(method_key, {})

        if isinstance(method_template, dict):
            template = method_template.get(self.language, method_key)
            if args and '{}' in template:
                return template.format(*args)
            return template
        return method_key


# 전역 설정 인스턴스
_global_config = None


def get_config(language: str = 'ko') -> FeedbackConfig:
    """전역 설정 인스턴스 가져오기"""
    global _global_config
    if _global_config is None:
        _global_config = FeedbackConfig(language=language)
    return _global_config


def set_language(language: str):
    """전역 언어 설정"""
    config = get_config()
    config.switch_language(language)