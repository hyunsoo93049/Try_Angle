"""
TryAngle v1.5 - Real-time Feedback Engine
실시간 피드백 생성 엔진
"""

import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FrameAnalysis:
    """실시간 프레임 분석 결과"""
    person_bbox: Optional[Tuple[float, float, float, float]]  # x1, y1, x2, y2 (normalized)
    pose_type: str  # closeup, medium_shot, knee_shot, full_shot
    aspect_ratio: str  # 16:9, 4:3, 1:1
    orientation: str  # landscape, portrait, square
    margins: Tuple[float, float, float, float]  # top, right, bottom, left
    person_position: Tuple[float, float]  # center_x, center_y
    compression_index: float  # 0.0 ~ 1.0


@dataclass
class FeedbackResult:
    """피드백 결과"""
    overall_score: float  # 0-100
    margin_feedback: str
    position_feedback: str
    compression_feedback: str
    action_suggestion: str
    confidence: float
    matched_pattern_key: str


class FeedbackEngine:
    """
    실시간 피드백 생성 엔진

    프레임별 분석 결과를 받아서 패턴과 비교하여 피드백 생성
    """

    def __init__(self, pattern_file: str):
        """
        Args:
            pattern_file: 패턴 JSON 파일 경로
        """
        self.patterns = self._load_patterns(pattern_file)
        self.feedback_templates = self._init_feedback_templates()

    def _load_patterns(self, pattern_file: str) -> Dict:
        """패턴 파일 로드"""
        with open(pattern_file, 'r') as f:
            data = json.load(f)
        return data['patterns']

    def _init_feedback_templates(self) -> Dict:
        """피드백 템플릿 초기화"""
        return {
            # 여백 피드백
            'margin': {
                'too_tight': "여백이 너무 좁습니다. 조금 뒤로 물러나세요.",
                'too_loose': "여백이 너무 넓습니다. 조금 가까이 다가가세요.",
                'unbalanced_horizontal': "좌우 여백이 불균형합니다. 중앙 정렬을 맞춰주세요.",
                'unbalanced_vertical': "상하 여백이 불균형합니다. 높이를 조절해주세요.",
                'good': "여백이 적절합니다."
            },
            # 위치 피드백
            'position': {
                'too_left': "인물이 너무 왼쪽에 있습니다. 오른쪽으로 이동하세요.",
                'too_right': "인물이 너무 오른쪽에 있습니다. 왼쪽으로 이동하세요.",
                'too_high': "인물이 너무 위에 있습니다. 아래로 이동하세요.",
                'too_low': "인물이 너무 아래에 있습니다. 위로 이동하세요.",
                'good': "인물 위치가 적절합니다."
            },
            # 압축감 피드백
            'compression': {
                'too_compressed': "배경이 너무 압축되어 있습니다. 광각으로 전환하세요.",
                'too_wide': "배경이 너무 넓게 퍼져 있습니다. 망원으로 전환하세요.",
                'good': "배경 압축감이 적절합니다."
            }
        }

    def get_pattern_key(self, theme: str, analysis: FrameAnalysis) -> str:
        """
        패턴 키 생성 (fallback 적용)

        Args:
            theme: 테마 (cafe_indoor, park_nature 등)
            analysis: 프레임 분석 결과

        Returns:
            패턴 키 (예: "cafe_indoor_closeup_16:9")
        """
        # 1차: theme + pose_type + aspect_ratio
        key = f"{theme}_{analysis.pose_type}_{analysis.aspect_ratio}"
        if key in self.patterns:
            return key

        # 2차: theme + pose_type (aspect 무시)
        for aspect in ["16:9", "4:3", "1:1"]:
            key = f"{theme}_{analysis.pose_type}_{aspect}"
            if key in self.patterns:
                return key

        # 3차: theme만
        for pose in ["closeup", "medium_shot", "knee_shot", "full_shot"]:
            for aspect in ["16:9", "4:3", "1:1"]:
                key = f"{theme}_{pose}_{aspect}"
                if key in self.patterns:
                    return key

        # 4차: 기본값
        return "default_medium_shot_16:9"

    def calculate_margin_score(self,
                              current: Tuple[float, float, float, float],
                              target: List[float]) -> float:
        """
        여백 점수 계산

        Args:
            current: 현재 여백 (top, right, bottom, left)
            target: 목표 여백 [top, right, bottom, left]

        Returns:
            점수 (0-100)
        """
        # 각 방향별 차이 계산
        differences = []
        for i in range(4):
            diff = abs(current[i] - target[i])
            # 차이를 0-1 범위로 정규화 (0.2 이상 차이면 0점)
            score = max(0, 1 - (diff / 0.2))
            differences.append(score)

        # 평균 점수
        return np.mean(differences) * 100

    def calculate_position_score(self,
                                current: Tuple[float, float],
                                target: List[float]) -> float:
        """
        위치 점수 계산

        Args:
            current: 현재 위치 (center_x, center_y)
            target: 목표 위치 [center_x, center_y]

        Returns:
            점수 (0-100)
        """
        # 유클리드 거리 계산
        distance = np.sqrt((current[0] - target[0])**2 +
                          (current[1] - target[1])**2)

        # 거리를 점수로 변환 (0.3 이상이면 0점)
        score = max(0, 1 - (distance / 0.3))
        return score * 100

    def calculate_compression_score(self,
                                   current: float,
                                   target: float) -> float:
        """
        압축감 점수 계산

        Args:
            current: 현재 압축감 지수
            target: 목표 압축감 지수

        Returns:
            점수 (0-100)
        """
        diff = abs(current - target)
        # 0.3 이상 차이면 0점
        score = max(0, 1 - (diff / 0.3))
        return score * 100

    def generate_margin_feedback(self,
                                current: Tuple[float, float, float, float],
                                target: List[float]) -> str:
        """여백 피드백 생성"""
        top, right, bottom, left = current
        t_top, t_right, t_bottom, t_left = target

        # 전체적으로 너무 좁은지/넓은지 체크
        current_avg = np.mean([top, right, bottom, left])
        target_avg = np.mean(target)

        if current_avg < target_avg - 0.05:
            return self.feedback_templates['margin']['too_tight']
        elif current_avg > target_avg + 0.05:
            return self.feedback_templates['margin']['too_loose']

        # 좌우 균형 체크
        if abs(left - right) > 0.05:
            return self.feedback_templates['margin']['unbalanced_horizontal']

        # 상하 균형 체크
        if abs(top - bottom) > 0.05:
            return self.feedback_templates['margin']['unbalanced_vertical']

        return self.feedback_templates['margin']['good']

    def generate_position_feedback(self,
                                  current: Tuple[float, float],
                                  target: List[float]) -> str:
        """위치 피드백 생성"""
        cx, cy = current
        tx, ty = target

        # 좌우 체크
        if cx < tx - 0.1:
            return self.feedback_templates['position']['too_left']
        elif cx > tx + 0.1:
            return self.feedback_templates['position']['too_right']

        # 상하 체크
        if cy < ty - 0.1:
            return self.feedback_templates['position']['too_high']
        elif cy > ty + 0.1:
            return self.feedback_templates['position']['too_low']

        return self.feedback_templates['position']['good']

    def generate_compression_feedback(self, current: float, target: float) -> str:
        """압축감 피드백 생성"""
        if current > target + 0.15:
            return self.feedback_templates['compression']['too_compressed']
        elif current < target - 0.15:
            return self.feedback_templates['compression']['too_wide']
        return self.feedback_templates['compression']['good']

    def generate_action_suggestion(self,
                                  margin_score: float,
                                  position_score: float,
                                  compression_score: float) -> str:
        """행동 제안 생성"""
        # 가장 낮은 점수 항목 찾기
        scores = {
            'margin': margin_score,
            'position': position_score,
            'compression': compression_score
        }

        worst = min(scores, key=scores.get)

        if scores[worst] > 80:
            return "완벽한 구도입니다! 촬영하세요."
        elif scores[worst] > 60:
            return "좋은 구도입니다. 미세 조정 후 촬영하세요."
        else:
            if worst == 'margin':
                return "여백을 조정한 후 촬영하세요."
            elif worst == 'position':
                return "인물 위치를 조정한 후 촬영하세요."
            else:
                return "카메라 렌즈를 조정한 후 촬영하세요."

    def analyze(self, theme: str, analysis: FrameAnalysis) -> FeedbackResult:
        """
        프레임 분석 및 피드백 생성

        Args:
            theme: 현재 테마
            analysis: 프레임 분석 결과

        Returns:
            FeedbackResult
        """
        # 패턴 키 찾기
        pattern_key = self.get_pattern_key(theme, analysis)

        # 패턴이 없으면 기본값 사용
        if pattern_key not in self.patterns:
            # 기본 패턴 생성
            pattern = {
                'm': [0.15, 0.15, 0.15, 0.15],  # 균등 여백
                'p': [0.5, 0.5],  # 중앙
                'c': 0.5  # 중간 압축
            }
        else:
            pattern = self.patterns[pattern_key]

        # 점수 계산
        margin_score = self.calculate_margin_score(
            analysis.margins, pattern['m']
        )
        position_score = self.calculate_position_score(
            analysis.person_position, pattern['p']
        )
        compression_score = self.calculate_compression_score(
            analysis.compression_index, pattern['c']
        )

        # 전체 점수 (가중 평균)
        overall_score = (
            margin_score * 0.5 +  # 여백 50%
            position_score * 0.3 +  # 위치 30%
            compression_score * 0.2  # 압축감 20%
        )

        # 피드백 생성
        margin_feedback = self.generate_margin_feedback(
            analysis.margins, pattern['m']
        )
        position_feedback = self.generate_position_feedback(
            analysis.person_position, pattern['p']
        )
        compression_feedback = self.generate_compression_feedback(
            analysis.compression_index, pattern['c']
        )

        # 행동 제안
        action_suggestion = self.generate_action_suggestion(
            margin_score, position_score, compression_score
        )

        # 신뢰도 계산 (패턴 매칭 정확도 기반)
        if pattern_key == self.get_pattern_key(theme, analysis):
            confidence = 0.95
        elif theme in pattern_key:
            confidence = 0.80
        else:
            confidence = 0.60

        return FeedbackResult(
            overall_score=overall_score,
            margin_feedback=margin_feedback,
            position_feedback=position_feedback,
            compression_feedback=compression_feedback,
            action_suggestion=action_suggestion,
            confidence=confidence,
            matched_pattern_key=pattern_key
        )


# ============================================================
# 사용 예시
# ============================================================
if __name__ == "__main__":
    # 엔진 초기화
    engine = FeedbackEngine("patterns_app_v1.json")

    # 테스트 분석 결과
    test_analysis = FrameAnalysis(
        person_bbox=(0.3, 0.2, 0.7, 0.8),
        pose_type="medium_shot",
        aspect_ratio="16:9",
        orientation="landscape",
        margins=(0.2, 0.15, 0.2, 0.15),
        person_position=(0.5, 0.5),
        compression_index=0.6
    )

    # 피드백 생성
    result = engine.analyze("cafe_indoor", test_analysis)

    print(f"Overall Score: {result.overall_score:.1f}")
    print(f"Margin: {result.margin_feedback}")
    print(f"Position: {result.position_feedback}")
    print(f"Compression: {result.compression_feedback}")
    print(f"Action: {result.action_suggestion}")
    print(f"Confidence: {result.confidence:.2f}")