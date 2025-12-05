"""
TryAngle v1.5 - Unified Feedback System
통합 피드백 시스템: 레퍼런스 비교 + 패턴 기반 피드백
"""

import os
import sys
import json
import time
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# 경로 추가
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "v1.5_learning"))

from reference_comparison import ReferenceComparison, ComparisonResult
from test_feedback_system import FeedbackSystemTester


@dataclass
class UnifiedFeedback:
    """통합 피드백 결과"""
    # 기본 정보
    image_path: str
    theme: str

    # 두 가지 피드백 모드
    pattern_feedback: Optional[Dict] = None
    reference_feedback: Optional[ComparisonResult] = None

    # 통합 점수 및 액션
    unified_score: float = 0.0
    primary_actions: List[Dict] = None
    confidence: float = 0.0

    # 시각적 가이드
    visual_overlay: Dict = None

    # 타이밍
    total_time: float = 0.0


class UnifiedFeedbackSystem:
    """통합 피드백 시스템"""

    def __init__(self, pattern_file: str = None):
        """
        초기화

        Args:
            pattern_file: 패턴 데이터베이스 경로
        """
        print("[UnifiedSystem] Initializing...")

        # 패턴 기반 피드백 시스템
        self.pattern_system = FeedbackSystemTester()

        # 레퍼런스 비교 시스템
        self.reference_system = ReferenceComparison()

        # 캐시
        self.feedback_cache = {}

        print("[UnifiedSystem] Ready!")

    def analyze_with_reference(self,
                              current_path: str,
                              reference_path: str,
                              theme: str = "auto",
                              weight: float = 0.7) -> UnifiedFeedback:
        """
        레퍼런스 이미지와 비교하여 피드백 생성

        Args:
            current_path: 평가할 이미지
            reference_path: 레퍼런스 이미지
            theme: 테마 (auto면 자동 감지)
            weight: 레퍼런스 비교 가중치 (0.0-1.0)
        """
        print("\n" + "="*60)
        print("Unified Feedback Analysis (with Reference)")
        print("="*60)

        start_time = time.time()

        # 1. 레퍼런스 비교
        print("\n[Phase 1] Reference Comparison")
        try:
            reference_result = self.reference_system.compare(
                current_path, reference_path, mode='detailed'
            )
            print(f"  - Similarity: {reference_result.similarity_score:.1f}/100")
        except Exception as e:
            print(f"  - Error: {e}")
            reference_result = None
            weight = 0.0  # 실패시 패턴만 사용

        # 2. 패턴 기반 피드백
        print("\n[Phase 2] Pattern-based Analysis")
        try:
            pattern_result = self.pattern_system.analyze_image(current_path, theme)
            if pattern_result["status"] == "success":
                print(f"  - Score: {pattern_result['feedback']['overall_score']:.1f}/100")
                print(f"  - Matched: {pattern_result['feedback']['matched_pattern']}")
            else:
                print(f"  - Error: {pattern_result.get('message', 'Unknown')}")
                pattern_result = None
        except Exception as e:
            print(f"  - Error: {e}")
            pattern_result = None

        # 3. 통합 점수 계산
        unified_score = self._calculate_unified_score(
            reference_result, pattern_result, weight
        )

        # 4. 우선순위 액션 생성
        primary_actions = self._merge_actions(
            reference_result, pattern_result, weight
        )

        # 5. 시각적 오버레이 생성
        visual_overlay = self._create_visual_overlay(
            current_path, reference_result, pattern_result
        )

        # 6. 신뢰도 계산
        confidence = self._calculate_confidence(
            reference_result, pattern_result, weight
        )

        # 결과 생성
        return UnifiedFeedback(
            image_path=current_path,
            theme=theme if theme != "auto" else self._detect_theme(current_path),
            pattern_feedback=pattern_result if pattern_result and pattern_result["status"] == "success" else None,
            reference_feedback=reference_result,
            unified_score=unified_score,
            primary_actions=primary_actions,
            confidence=confidence,
            visual_overlay=visual_overlay,
            total_time=time.time() - start_time
        )

    def analyze_with_pattern(self,
                            image_path: str,
                            theme: str = "auto") -> UnifiedFeedback:
        """
        패턴 데이터베이스만 사용하여 피드백 생성

        Args:
            image_path: 평가할 이미지
            theme: 테마
        """
        print("\n" + "="*60)
        print("Unified Feedback Analysis (Pattern-only)")
        print("="*60)

        start_time = time.time()

        # 패턴 기반 피드백
        print("\n[Analysis] Pattern-based feedback")
        try:
            pattern_result = self.pattern_system.analyze_image(image_path, theme)

            if pattern_result["status"] == "success":
                # 패턴 피드백을 액션으로 변환
                actions = self._convert_pattern_to_actions(pattern_result)

                # 시각적 오버레이
                visual_overlay = self._create_pattern_overlay(
                    image_path, pattern_result
                )

                return UnifiedFeedback(
                    image_path=image_path,
                    theme=theme if theme != "auto" else pattern_result.get("theme", "unknown"),
                    pattern_feedback=pattern_result,
                    reference_feedback=None,
                    unified_score=pattern_result['feedback']['overall_score'],
                    primary_actions=actions,
                    confidence=pattern_result['feedback']['confidence'],
                    visual_overlay=visual_overlay,
                    total_time=time.time() - start_time
                )
            else:
                raise ValueError(pattern_result.get('message', 'Analysis failed'))

        except Exception as e:
            print(f"  - Error: {e}")
            return UnifiedFeedback(
                image_path=image_path,
                theme=theme,
                pattern_feedback=None,
                reference_feedback=None,
                unified_score=0.0,
                primary_actions=[],
                confidence=0.0,
                visual_overlay=None,
                total_time=time.time() - start_time
            )

    def _calculate_unified_score(self,
                                reference_result: Optional[ComparisonResult],
                                pattern_result: Optional[Dict],
                                weight: float) -> float:
        """통합 점수 계산"""

        scores = []
        weights = []

        if reference_result:
            scores.append(reference_result.similarity_score)
            weights.append(weight)

        if pattern_result and pattern_result.get("status") == "success":
            scores.append(pattern_result['feedback']['overall_score'])
            weights.append(1.0 - weight if reference_result else 1.0)

        if not scores:
            return 0.0

        # 가중 평균
        return sum(s * w for s, w in zip(scores, weights)) / sum(weights)

    def _merge_actions(self,
                      reference_result: Optional[ComparisonResult],
                      pattern_result: Optional[Dict],
                      weight: float) -> List[Dict]:
        """액션 병합 및 우선순위 결정"""

        actions = []

        # 레퍼런스 기반 액션
        if reference_result and reference_result.priority_actions:
            for action in reference_result.priority_actions:
                action_copy = action.copy()
                action_copy['source'] = 'reference'
                action_copy['weight'] = weight
                actions.append(action_copy)

        # 패턴 기반 액션
        if pattern_result and pattern_result.get("status") == "success":
            pattern_actions = self._convert_pattern_to_actions(pattern_result)
            for action in pattern_actions:
                action['source'] = 'pattern'
                action['weight'] = 1.0 - weight if reference_result else 1.0
                actions.append(action)

        # 중복 제거 및 우선순위 정렬
        unique_actions = self._deduplicate_actions(actions)

        # 가중치 기반 정렬
        unique_actions.sort(key=lambda x: x.get('weight', 0), reverse=True)

        # 상위 3개 반환
        return unique_actions[:3]

    def _convert_pattern_to_actions(self, pattern_result: Dict) -> List[Dict]:
        """패턴 피드백을 액션 형식으로 변환"""

        actions = []
        feedback = pattern_result.get('feedback', {})
        analysis = pattern_result.get('analysis', {})

        # 여백 피드백을 액션으로
        margin_feedback = feedback.get('margin_feedback', '')
        if '너무 좁' in margin_feedback or 'too tight' in margin_feedback.lower():
            actions.append({
                'type': 'margin',
                'action': 'Zoom out',
                'direction': '⟵⟶',
                'amount': '10-15%',
                'impact': '+10 points'
            })
        elif '너무 넓' in margin_feedback or 'too loose' in margin_feedback.lower():
            actions.append({
                'type': 'margin',
                'action': 'Zoom in',
                'direction': '⟶⟵',
                'amount': '10-15%',
                'impact': '+10 points'
            })

        # 위치 피드백을 액션으로
        position_feedback = feedback.get('position_feedback', '')
        if '위로' in position_feedback or 'move up' in position_feedback.lower():
            actions.append({
                'type': 'position',
                'action': 'Move up',
                'direction': '↑',
                'amount': '5-10%',
                'impact': '+5 points'
            })
        elif '아래로' in position_feedback or 'move down' in position_feedback.lower():
            actions.append({
                'type': 'position',
                'action': 'Move down',
                'direction': '↓',
                'amount': '5-10%',
                'impact': '+5 points'
            })

        # 압축감 피드백을 액션으로
        compression_feedback = feedback.get('compression_feedback', '')
        if '망원' in compression_feedback or 'telephoto' in compression_feedback.lower():
            actions.append({
                'type': 'compression',
                'action': 'Use telephoto lens',
                'direction': '🔭',
                'amount': '85mm+',
                'impact': '+15 points'
            })
        elif '광각' in compression_feedback or 'wide' in compression_feedback.lower():
            actions.append({
                'type': 'compression',
                'action': 'Use wider lens',
                'direction': '📐',
                'amount': '24-35mm',
                'impact': '+15 points'
            })

        return actions

    def _deduplicate_actions(self, actions: List[Dict]) -> List[Dict]:
        """중복 액션 제거"""

        unique = {}
        for action in actions:
            key = f"{action['type']}_{action.get('direction', '')}"
            if key not in unique:
                unique[key] = action
            else:
                # 더 높은 가중치 유지
                if action.get('weight', 0) > unique[key].get('weight', 0):
                    unique[key] = action

        return list(unique.values())

    def _calculate_confidence(self,
                            reference_result: Optional[ComparisonResult],
                            pattern_result: Optional[Dict],
                            weight: float) -> float:
        """신뢰도 계산"""

        confidences = []
        weights = []

        if reference_result:
            # 레퍼런스 비교는 일반적으로 높은 신뢰도
            confidences.append(0.95)
            weights.append(weight)

        if pattern_result and pattern_result.get("status") == "success":
            confidences.append(pattern_result['feedback'].get('confidence', 0.8))
            weights.append(1.0 - weight if reference_result else 1.0)

        if not confidences:
            return 0.0

        return sum(c * w for c, w in zip(confidences, weights)) / sum(weights)

    def _create_visual_overlay(self,
                              image_path: str,
                              reference_result: Optional[ComparisonResult],
                              pattern_result: Optional[Dict]) -> Dict:
        """시각적 오버레이 정보 생성"""

        overlay = {
            'current_bbox': None,
            'target_bbox': None,
            'movement_arrows': [],
            'grid_lines': {
                'rule_of_thirds': True,
                'golden_ratio': False
            },
            'margin_guides': None,
            'focus_point': None
        }

        # 레퍼런스 결과에서 오버레이 정보
        if reference_result and reference_result.visual_guides:
            guides = reference_result.visual_guides
            overlay['current_bbox'] = guides.get('current_bbox')
            overlay['target_bbox'] = guides.get('target_area')

            if guides.get('movement_arrow'):
                arrow = guides['movement_arrow']
                overlay['movement_arrows'].append({
                    'from': arrow['start'],
                    'to': arrow['end'],
                    'strength': min(1.0, arrow['distance'] * 2),
                    'color': 'green'
                })

        # 패턴 결과에서 추가 정보
        if pattern_result and pattern_result.get("status") == "success":
            detection = pattern_result.get('detection', {})
            if detection.get('person_bbox'):
                overlay['current_bbox'] = detection['person_bbox']

            analysis = pattern_result.get('analysis', {})
            if analysis.get('center'):
                overlay['focus_point'] = analysis['center']

            # 여백 가이드
            if analysis.get('margins'):
                margins = analysis['margins']
                overlay['margin_guides'] = {
                    'top': margins[0],
                    'right': margins[1],
                    'bottom': margins[2],
                    'left': margins[3],
                    'optimal': self._get_optimal_margins(pattern_result)
                }

        return overlay

    def _create_pattern_overlay(self,
                               image_path: str,
                               pattern_result: Dict) -> Dict:
        """패턴 전용 오버레이"""

        overlay = {
            'current_bbox': pattern_result.get('detection', {}).get('person_bbox'),
            'grid_lines': {'rule_of_thirds': True},
            'margin_guides': None,
            'focus_point': pattern_result.get('analysis', {}).get('center')
        }

        # 여백 가이드
        margins = pattern_result.get('analysis', {}).get('margins')
        if margins:
            overlay['margin_guides'] = {
                'top': margins[0],
                'right': margins[1],
                'bottom': margins[2],
                'left': margins[3],
                'optimal': self._get_optimal_margins(pattern_result)
            }

        return overlay

    def _get_optimal_margins(self, pattern_result: Dict) -> Dict:
        """최적 여백 계산"""

        # 포즈 타입별 권장 여백
        pose_type = pattern_result.get('analysis', {}).get('pose_type', 'medium_shot')

        optimal = {
            'closeup': {'top': 0.05, 'sides': 0.05, 'bottom': 0.05},
            'medium_shot': {'top': 0.15, 'sides': 0.15, 'bottom': 0.20},
            'knee_shot': {'top': 0.20, 'sides': 0.15, 'bottom': 0.15},
            'full_shot': {'top': 0.15, 'sides': 0.20, 'bottom': 0.15}
        }

        return optimal.get(pose_type, optimal['medium_shot'])

    def _detect_theme(self, image_path: str) -> str:
        """이미지에서 테마 자동 감지"""
        # 간단한 규칙 기반 감지
        # 실제로는 더 복잡한 분류기 사용 가능

        path_lower = image_path.lower()

        if 'cafe' in path_lower or 'coffee' in path_lower:
            return 'cafe_indoor'
        elif 'park' in path_lower or 'nature' in path_lower:
            return 'park_nature'
        elif 'street' in path_lower or 'urban' in path_lower:
            return 'street_urban'
        elif 'winter' in path_lower or 'snow' in path_lower:
            return 'winter'
        else:
            return 'indoor_home'

    def create_visualization(self,
                            feedback: UnifiedFeedback,
                            output_path: str = None) -> Optional[str]:
        """
        피드백 시각화 이미지 생성

        Args:
            feedback: 통합 피드백 결과
            output_path: 저장 경로

        Returns:
            저장된 파일 경로
        """
        try:
            # 원본 이미지 로드
            image = Image.open(feedback.image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # 오버레이 그리기
            draw = ImageDraw.Draw(image, 'RGBA')
            width, height = image.size

            overlay = feedback.visual_overlay
            if not overlay:
                return None

            # 1. Rule of thirds 그리드
            if overlay.get('grid_lines', {}).get('rule_of_thirds'):
                for x in [width/3, 2*width/3]:
                    draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 50), width=1)
                for y in [height/3, 2*height/3]:
                    draw.line([(0, y), (width, y)], fill=(255, 255, 255, 50), width=1)

            # 2. 현재 바운딩 박스
            if overlay.get('current_bbox'):
                x1, y1, x2, y2 = overlay['current_bbox']
                x1, y1, x2, y2 = x1*width, y1*height, x2*width, y2*height
                draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0, 200), width=3)

            # 3. 목표 바운딩 박스
            if overlay.get('target_bbox'):
                x1, y1, x2, y2 = overlay['target_bbox']
                x1, y1, x2, y2 = x1*width, y1*height, x2*width, y2*height
                draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 0, 150), width=2)

            # 4. 이동 화살표
            for arrow in overlay.get('movement_arrows', []):
                start = (arrow['from'][0]*width, arrow['from'][1]*height)
                end = (arrow['to'][0]*width, arrow['to'][1]*height)
                draw.line([start, end], fill=(0, 255, 0, 200), width=3)

                # 화살표 머리
                angle = np.arctan2(end[1]-start[1], end[0]-start[0])
                arrow_len = 20
                draw.line([end, (end[0]-arrow_len*np.cos(angle-0.5),
                                end[1]-arrow_len*np.sin(angle-0.5))],
                         fill=(0, 255, 0, 200), width=3)
                draw.line([end, (end[0]-arrow_len*np.cos(angle+0.5),
                                end[1]-arrow_len*np.sin(angle+0.5))],
                         fill=(0, 255, 0, 200), width=3)

            # 5. 액션 텍스트 오버레이
            y_offset = 20
            for i, action in enumerate(feedback.primary_actions[:3]):
                text = f"{i+1}. {action['action']} {action['direction']} ({action['amount']})"
                draw.text((20, y_offset), text,
                         fill=(255, 255, 0, 255),
                         font=None)
                y_offset += 30

            # 6. 점수 표시
            score_text = f"Score: {feedback.unified_score:.1f}/100"
            draw.text((width-150, 20), score_text,
                     fill=(255, 255, 255, 255),
                     font=None)

            # 저장
            if not output_path:
                output_path = feedback.image_path.replace('.', '_feedback.')

            image.save(output_path, quality=95)
            print(f"\n[Visualization] Saved to: {output_path}")
            return output_path

        except Exception as e:
            print(f"\n[Visualization Error] {e}")
            return None


def print_unified_feedback(feedback: UnifiedFeedback):
    """통합 피드백 결과 출력"""

    print("\n" + "="*60)
    print("UNIFIED FEEDBACK RESULTS")
    print("="*60)

    # 기본 정보
    print(f"\nImage: {Path(feedback.image_path).name}")
    print(f"Theme: {feedback.theme}")
    print(f"Analysis Time: {feedback.total_time:.2f}s")
    print(f"Confidence: {feedback.confidence:.1%}")

    # 통합 점수
    score_emoji = "🟢" if feedback.unified_score >= 80 else "🟡" if feedback.unified_score >= 60 else "🔴"
    print(f"\n{score_emoji} Unified Score: {feedback.unified_score:.1f}/100")

    # 우선순위 액션
    if feedback.primary_actions:
        print("\n📋 Recommended Actions:")
        for i, action in enumerate(feedback.primary_actions):
            print(f"\n  {i+1}. {action['action']} {action.get('direction', '')}")
            print(f"     Amount: {action.get('amount', 'N/A')}")
            print(f"     Expected Impact: {action.get('impact', 'N/A')}")
            print(f"     Source: {action.get('source', 'unified')}")

    # 상세 피드백 (있는 경우)
    if feedback.reference_feedback:
        print("\n📊 Reference Comparison:")
        print(f"   Similarity: {feedback.reference_feedback.similarity_score:.1f}/100")
        print(f"   Position Difference: {feedback.reference_feedback.position_difference}")
        print(f"   Margin Differences: {feedback.reference_feedback.margin_differences}")

    if feedback.pattern_feedback:
        pf = feedback.pattern_feedback.get('feedback', {})
        print("\n📊 Pattern Analysis:")
        print(f"   Pattern Score: {pf.get('overall_score', 0):.1f}/100")
        print(f"   Matched Pattern: {pf.get('matched_pattern', 'N/A')}")
        print(f"   Margin Feedback: {pf.get('margin_feedback', 'N/A')}")

    # 시각적 가이드 정보
    if feedback.visual_overlay:
        print("\n🎯 Visual Guides Available:")
        if feedback.visual_overlay.get('target_bbox'):
            print("   - Target area overlay")
        if feedback.visual_overlay.get('movement_arrows'):
            print("   - Movement direction arrows")
        if feedback.visual_overlay.get('margin_guides'):
            print("   - Margin adjustment guides")
        if feedback.visual_overlay.get('grid_lines'):
            print("   - Composition grid lines")

    print("\n" + "="*60)


# ============================================================
# 테스트 함수
# ============================================================

def test_unified_system():
    """통합 시스템 테스트"""

    print("\n" + "="*60)
    print("TryAngle v1.5 - Unified Feedback System Test")
    print("="*60)

    # 시스템 초기화
    system = UnifiedFeedbackSystem()

    # 테스트 케이스
    test_cases = [
        # 1. 레퍼런스 비교 테스트
        {
            'mode': 'reference',
            'current': 'C:/try_angle/data/sample_images/cafe2.jpg',
            'reference': 'C:/try_angle/data/sample_images/cafe1.jpg',
            'theme': 'cafe_indoor'
        },
        # 2. 패턴만 사용 테스트
        {
            'mode': 'pattern',
            'current': 'C:/try_angle/data/sample_images/cafe1.jpg',
            'theme': 'cafe_indoor'
        }
    ]

    results = []

    for i, test in enumerate(test_cases):
        print(f"\n[Test {i+1}] Mode: {test['mode']}")
        print("-" * 40)

        try:
            if test['mode'] == 'reference':
                # 레퍼런스 비교 모드
                feedback = system.analyze_with_reference(
                    test['current'],
                    test['reference'],
                    test['theme'],
                    weight=0.7
                )
            else:
                # 패턴 전용 모드
                feedback = system.analyze_with_pattern(
                    test['current'],
                    test['theme']
                )

            # 결과 출력
            print_unified_feedback(feedback)

            # 시각화 생성
            viz_path = system.create_visualization(
                feedback,
                f"test_feedback_{i+1}.jpg"
            )

            results.append({
                'test': test,
                'feedback': asdict(feedback),
                'visualization': viz_path
            })

        except Exception as e:
            print(f"\n[Error] {e}")
            import traceback
            traceback.print_exc()

    # 결과 저장
    with open('unified_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print("\n[Complete] Test results saved to unified_test_results.json")


if __name__ == "__main__":
    test_unified_system()