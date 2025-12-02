"""
TryAngle v1.5 - Configuration Manager

YAML 기반 설정 관리 시스템
- 피드백 룰 설정 (thresholds, priorities, impact scores)
- 다국어 메시지 관리 (한국어/영어)
- 모델 설정 관리
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import os


class ConfigManager:
    """
    설정 관리 클래스

    Usage:
        config = ConfigManager(config_dir="config", language="ko")

        # 룰 설정 가져오기
        threshold = config.get_rule("aspect_ratio", "threshold")
        priority = config.get_rule("position", "priority")

        # 메시지 가져오기
        message = config.get_message("feedback.aspect_ratio.change")

        # 모델 설정 가져오기
        model_path = config.get_model_config("grounding_dino", "checkpoint")
    """

    def __init__(self,
                 config_dir: Optional[str] = None,
                 language: str = "ko"):
        """
        Args:
            config_dir: 설정 디렉토리 경로 (기본: src/v1.5_realtime/config)
            language: 메시지 언어 (ko/en)
        """
        # 기본 경로: src/v1.5_realtime/config
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config"
        else:
            config_dir = Path(config_dir)

        self.config_dir = config_dir
        self.language = language

        # 설정 캐시
        self._rules: Optional[Dict[str, Any]] = None
        self._messages: Optional[Dict[str, Any]] = None
        self._models: Optional[Dict[str, Any]] = None

        print(f"[ConfigManager] 초기화 (언어: {language})")
        print(f"[ConfigManager] 설정 디렉토리: {config_dir}")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """YAML 파일 로드"""
        filepath = self.config_dir / filename

        if not filepath.exists():
            print(f"[ConfigManager] ⚠️  파일 없음: {filepath}")
            return {}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                print(f"[ConfigManager] ✅ 로드 성공: {filename}")
                return data
        except Exception as e:
            print(f"[ConfigManager] ❌ 로드 실패: {filename} - {e}")
            return {}

    def get_rule(self, rule_name: str, key: Optional[str] = None) -> Any:
        """
        룰 설정 가져오기

        Args:
            rule_name: 룰 이름 (aspect_ratio, position, compression, margin)
            key: 설정 키 (threshold, priority, impact_score 등)
                 None이면 전체 룰 설정 반환

        Returns:
            설정 값 또는 룰 설정 딕셔너리

        Example:
            threshold = config.get_rule("aspect_ratio", "threshold")  # 0.1
            rule = config.get_rule("aspect_ratio")  # 전체 설정
        """
        # 캐시에서 로드 (지연 로딩)
        if self._rules is None:
            self._rules = self._load_yaml("feedback_rules.yaml")

        if rule_name not in self._rules:
            print(f"[ConfigManager] ⚠️  룰 없음: {rule_name}")
            return None

        rule = self._rules[rule_name]

        if key is None:
            return rule

        return rule.get(key)

    def get_message(self, message_key: str, **kwargs) -> str:
        """
        메시지 가져오기 (템플릿 지원)

        Args:
            message_key: 점 표기법 키 (feedback.aspect_ratio.change)
            **kwargs: 템플릿 변수 (예: target="16:9")

        Returns:
            포맷팅된 메시지 문자열

        Example:
            msg = config.get_message("feedback.aspect_ratio.description", target="16:9")
            # → "16:9로 변경하세요"
        """
        # 캐시에서 로드 (지연 로딩)
        if self._messages is None:
            filename = f"messages_{self.language}.yaml"
            self._messages = self._load_yaml(filename)

        # 점 표기법으로 중첩된 딕셔너리 접근
        keys = message_key.split('.')
        value = self._messages

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                print(f"[ConfigManager] ⚠️  메시지 없음: {message_key}")
                return message_key  # 키 자체를 반환

        if value is None:
            print(f"[ConfigManager] ⚠️  메시지 없음: {message_key}")
            return message_key

        # 템플릿 변수 치환
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as e:
                print(f"[ConfigManager] ⚠️  템플릿 변수 누락: {e}")
                return value

        return value

    def get_model_config(self, model_name: str, key: Optional[str] = None) -> Any:
        """
        모델 설정 가져오기

        Args:
            model_name: 모델 이름 (grounding_dino, depth_anything)
            key: 설정 키 (checkpoint, confidence_threshold 등)
                 None이면 전체 모델 설정 반환

        Returns:
            설정 값 또는 모델 설정 딕셔너리
        """
        # 캐시에서 로드 (지연 로딩)
        if self._models is None:
            self._models = self._load_yaml("models.yaml")

        if model_name not in self._models:
            print(f"[ConfigManager] ⚠️  모델 설정 없음: {model_name}")
            return None

        model = self._models[model_name]

        if key is None:
            return model

        return model.get(key)

    def get_all_rules(self) -> Dict[str, Any]:
        """모든 룰 설정 반환"""
        if self._rules is None:
            self._rules = self._load_yaml("feedback_rules.yaml")
        return self._rules

    def set_language(self, language: str):
        """
        언어 변경

        Args:
            language: 언어 코드 (ko/en)
        """
        if language != self.language:
            self.language = language
            self._messages = None  # 캐시 무효화
            print(f"[ConfigManager] 언어 변경: {language}")

    def reload(self):
        """모든 설정 파일 다시 로드"""
        self._rules = None
        self._messages = None
        self._models = None
        print("[ConfigManager] 설정 파일 다시 로드")

    def validate_config(self) -> bool:
        """
        설정 파일 검증

        Returns:
            True if all required config files exist and are valid
        """
        print("\n[ConfigManager] 설정 파일 검증")
        print("-" * 50)

        required_files = [
            "feedback_rules.yaml",
            f"messages_{self.language}.yaml",
            "models.yaml"
        ]

        all_valid = True
        for filename in required_files:
            filepath = self.config_dir / filename
            exists = filepath.exists()
            status = "✅" if exists else "❌"
            print(f"{status} {filename}")

            if not exists:
                all_valid = False

        print("-" * 50)
        return all_valid
