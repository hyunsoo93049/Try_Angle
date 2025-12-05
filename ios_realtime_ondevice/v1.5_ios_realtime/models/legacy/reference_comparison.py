"""
TryAngle v1.5 - Reference Image Comparison System
레퍼런스 이미지 기반 구도 비교 및 피드백 시스템
"""

import sys
import json
import time
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# 경로 추가
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "v1.5_learning"))
sys.path.append(str(Path(__file__).parent.parent / "v1.5_learning" / "models"))

from .grounding_dino import GroundingDINOWrapper
from ..depth_small_wrapper import DepthAnythingSmall as DepthAnythingWrapper


@dataclass
class ImageAnalysis:
    """이미지 분석 결과"""
    # 기본 정보
    file_path: str
    image_size: Tuple[int, int]  # (width, height)

    # 인물 정보
    person_bbox: Optional[Tuple[float, float, float, float]]  # normalized
    person_confidence: float

    # 구도 정보
    margins: Tuple[float, float, float, float]  # top, right, bottom, left
    person_position: Tuple[float, float]  # center_x, center_y
    pose_type: str

    # 깊이 정보
    compression_index: float
    camera_type: str
    person_depth: float
    background_depth: float

    # 추가 메타데이터
    aspect_ratio: str
    orientation: str
    analysis_time: float


@dataclass
class ComparisonResult:
    """비교 결과"""
    similarity_score: float  # 0-100

    # 차이 분석
    margin_differences: Dict[str, float]
    position_difference: Tuple[float, float]
    compression_difference: float

    # 구체적 피드백
    priority_actions: List[Dict]
    detailed_feedback: Dict
    visual_guides: Dict

    # 개선 예상 점수
    improvement_potential: float


class ReferenceComparison:
    """레퍼런스 이미지 비교 엔진"""

    def __init__(self):
        """초기화"""
        print("[System] Initializing Reference Comparison System...")

        # AI 모델 로드
        self.grounding_dino = GroundingDINOWrapper()
        self.depth_anything = DepthAnythingWrapper(device="cpu")

        # 캐시
        self.analysis_cache = {}

        print("[System] Ready!")

    def analyze_image(self, image_path: str) -> ImageAnalysis:
        """이미지 상세 분석"""

        # 캐시 확인
        if image_path in self.analysis_cache:
            print(f"[캐시] {Path(image_path).name} 캐시 사용")
            return self.analysis_cache[image_path]

        print(f"\n[분석 중] {Path(image_path).name}")
        start_time = time.time()

        # 이미지 로드
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        width, height = image.size

        # 1. 인물 감지 (Grounding DINO)
        print("  - 인물 감지 중...")
        dino_result = self.grounding_dino.detect(
            image,
            person_prompt="person",
            bg_prompts=["window", "table", "building", "tree"]
        )

        if not dino_result.person_bbox:
            raise ValueError(f"인물을 찾을 수 없습니다: {image_path}")

        # 2. 깊이 분석 (Depth Anything)
        print("  - 깊이 분석 중...")
        # Convert PIL to numpy array for our wrapper
        image_np = np.array(image)
        depth_map = self.depth_anything.process_frame(image_np)

        # Calculate compression using person bbox
        if depth_map is not None:
            # Convert normalized bbox to pixels
            h, w = image_np.shape[:2]
            bbox_pixels = [
                int(dino_result.person_bbox[0] * w),
                int(dino_result.person_bbox[1] * h),
                int(dino_result.person_bbox[2] * w),
                int(dino_result.person_bbox[3] * h)
            ] if dino_result.person_bbox else None

            compression_info = self.depth_anything.calculate_compression(depth_map, bbox_pixels)

            # Create depth_result object matching expected format
            depth_result = type('DepthResult', (), {
                'compression_index': compression_info['compression_index'],
                'camera_type': compression_info['camera_type'],
                'person_depth': compression_info['person_depth'],
                'background_depth': compression_info['background_depth']
            })()
        else:
            # Default values if depth fails
            depth_result = type('DepthResult', (), {
                'compression_index': 0.5,
                'camera_type': 'normal',
                'person_depth': 0.5,
                'background_depth': 0.5
            })()

        # 3. 구도 정보 계산
        margins = self._calculate_margins(dino_result.person_bbox)
        person_position = self._calculate_center(dino_result.person_bbox)
        pose_type = self._detect_pose_type(dino_result.person_bbox)
        aspect_ratio, orientation = self._get_aspect_ratio(width, height)

        # 분석 결과 생성
        analysis = ImageAnalysis(
            file_path=image_path,
            image_size=(width, height),
            person_bbox=dino_result.person_bbox,
            person_confidence=dino_result.person_confidence,
            margins=margins,
            person_position=person_position,
            pose_type=pose_type,
            compression_index=depth_result.compression_index,
            camera_type=depth_result.camera_type,
            person_depth=depth_result.person_depth,
            background_depth=depth_result.background_depth,
            aspect_ratio=aspect_ratio,
            orientation=orientation,
            analysis_time=time.time() - start_time
        )

        # 캐싱
        self.analysis_cache[image_path] = analysis

        print(f"  - 완료 시간: {analysis.analysis_time:.2f}초")
        return analysis

    def compare(self,
                current_path: str,
                reference_path: str,
                mode: str = 'detailed') -> ComparisonResult:
        """
        현재 이미지와 레퍼런스 비교

        Args:
            current_path: 평가할 이미지 경로
            reference_path: 레퍼런스 이미지 경로
            mode: 'quick' or 'detailed'
        """

        print("\n" + "="*60)
        print("레퍼런스 기반 비교")
        print("="*60)

        # 두 이미지 분석
        reference = self.analyze_image(reference_path)
        current = self.analyze_image(current_path)

        print("\n[비교 중] 차이점 계산 중...")

        # 0. 종횡비 체크 (최우선)
        aspect_ratio_check = self._check_aspect_ratio(current, reference)
        if aspect_ratio_check:
            # 종횡비가 다르면 이것만 피드백
            priority_actions = [aspect_ratio_check]
            similarity_score = 50.0  # 기본 점수
            margin_diffs = {}
            position_diff = (0, 0)
            compression_diff = 0
        else:
            # 1. 차이 계산
            margin_diffs = {
                'top': current.margins[0] - reference.margins[0],
                'right': current.margins[1] - reference.margins[1],
                'bottom': current.margins[2] - reference.margins[2],
                'left': current.margins[3] - reference.margins[3]
            }

            position_diff = (
                current.person_position[0] - reference.person_position[0],
                current.person_position[1] - reference.person_position[1]
            )

            compression_diff = current.compression_index - reference.compression_index

            # 2. 유사도 점수 계산
            similarity_score = self._calculate_similarity(
                current, reference, margin_diffs, position_diff, compression_diff
            )

            # 3. 통합 방향 계산 및 우선순위별 액션 생성
            priority_actions = self._generate_unified_actions(
                margin_diffs, position_diff, compression_diff
            )

        # 4. 상세 피드백 생성
        detailed_feedback = self._generate_detailed_feedback(
            current, reference, margin_diffs, position_diff, compression_diff
        )

        # 5. 시각적 가이드 생성
        visual_guides = self._generate_visual_guides(
            current, reference, margin_diffs, position_diff
        )

        # 6. 개선 가능 점수
        improvement_potential = min(100, similarity_score + len(priority_actions) * 10)

        return ComparisonResult(
            similarity_score=similarity_score,
            margin_differences=margin_diffs,
            position_difference=position_diff,
            compression_difference=compression_diff,
            priority_actions=priority_actions,
            detailed_feedback=detailed_feedback,
            visual_guides=visual_guides,
            improvement_potential=improvement_potential
        )

    def _calculate_similarity(self, current, reference, margin_diffs, position_diff, compression_diff):
        """유사도 점수 계산 (0-100)"""

        # 여백 차이 점수 (40%)
        margin_score = 100
        for diff in margin_diffs.values():
            margin_score -= abs(diff) * 100  # 0.1 차이 = -10점
        margin_score = max(0, margin_score) * 0.4

        # 위치 차이 점수 (30%)
        position_distance = np.sqrt(position_diff[0]**2 + position_diff[1]**2)
        position_score = max(0, 100 - position_distance * 200) * 0.3

        # 압축감 차이 점수 (20%)
        compression_score = max(0, 100 - abs(compression_diff) * 100) * 0.2

        # 포즈 타입 일치 점수 (10%)
        pose_score = 100 if current.pose_type == reference.pose_type else 50
        pose_score *= 0.1

        return margin_score + position_score + compression_score + pose_score

    def _check_aspect_ratio(self, current, reference):
        """종횡비 차이 체크"""

        # 종횡비가 다른지 확인
        if current.aspect_ratio != reference.aspect_ratio:
            return {
                'priority': 1,
                'type': 'aspect_ratio',
                'action': '카메라 종횡비 변경',
                'direction': '',
                'amount': f'{reference.aspect_ratio}로 변경',
                'current': current.aspect_ratio,
                'target': reference.aspect_ratio,
                'impact': '+30점 (필수 조건)'
            }
        return None

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

    def _generate_unified_actions(self, margin_diffs, position_diff, compression_diff):
        """통합된 우선순위별 개선 액션 생성"""

        actions = []

        # 통합 방향 계산
        h_move, v_move = self._calculate_unified_direction(margin_diffs, position_diff)

        # 통합 이동 액션 (하나의 방향만)
        if abs(h_move) > 0.03 or abs(v_move) > 0.03:
            direction_str = ""
            direction_arrow = ""

            if abs(v_move) > abs(h_move):  # 수직이 더 큼
                if v_move > 0:
                    direction_str = "위로"
                    direction_arrow = "↑"
                else:
                    direction_str = "아래로"
                    direction_arrow = "↓"
                amount = f"{abs(v_move)*100:.0f}%"
            else:  # 수평이 더 큼
                if h_move > 0:
                    direction_str = "오른쪽으로"
                    direction_arrow = "→"
                else:
                    direction_str = "왼쪽으로"
                    direction_arrow = "←"
                amount = f"{abs(h_move)*100:.0f}%"

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

            actions.append({
                'priority': 1,
                'type': 'position',
                'action': f'카메라 {direction_str} 이동',
                'direction': direction_arrow,
                'amount': amount,
                'impact': f'+{max(abs(h_move), abs(v_move))*50:.0f}점'
            })

        # 압축감 조정 액션
        if abs(compression_diff) > 0.1:
            if compression_diff > 0:
                action = "광각 렌즈로 변경"
                detail = "24-35mm 추천"
            else:
                action = "망원 렌즈로 변경"
                detail = "85mm 이상 추천"

            actions.append({
                'priority': len(actions) + 1,
                'type': 'compression',
                'action': action,
                'amount': detail,
                'direction': '',
                'impact': f'+{abs(compression_diff)*20:.0f}점'
            })

        return actions[:3]  # 상위 3개만 반환

    def _generate_priority_actions(self, margin_diffs, position_diff, compression_diff):
        """(구버전 - 호환성 유지용)"""
        return self._generate_unified_actions(margin_diffs, position_diff, compression_diff)

    def _generate_detailed_feedback(self, current, reference, margin_diffs, position_diff, compression_diff):
        """상세 피드백 생성"""

        feedback = {
            'summary': '',
            'margins': {},
            'position': {},
            'compression': {},
            'pose': {}
        }

        # 전체 요약
        if margin_diffs and all(abs(d) < 0.05 for d in margin_diffs.values()) and \
           all(abs(p) < 0.05 for p in position_diff) and \
           abs(compression_diff) < 0.1:
            feedback['summary'] = "훌륭합니다! 레퍼런스와 매우 유사합니다."
        else:
            feedback['summary'] = "좋은 시도입니다. 약간의 조정이 필요합니다."

        # 여백 피드백
        if margin_diffs:
            feedback['margins'] = {
                'current': f"상:{current.margins[0]:.0%} 우:{current.margins[1]:.0%} 하:{current.margins[2]:.0%} 좌:{current.margins[3]:.0%}",
                'reference': f"상:{reference.margins[0]:.0%} 우:{reference.margins[1]:.0%} 하:{reference.margins[2]:.0%} 좌:{reference.margins[3]:.0%}",
                'status': '좋음' if max(abs(d) for d in margin_diffs.values()) < 0.05 else '조정 필요'
            }
        else:
            feedback['margins'] = {'status': '종횡비 우선 조정'}

        # 위치 피드백
        feedback['position'] = {
            'current': f"({current.person_position[0]:.2f}, {current.person_position[1]:.2f})",
            'reference': f"({reference.person_position[0]:.2f}, {reference.person_position[1]:.2f})",
            'distance': f"{np.sqrt(position_diff[0]**2 + position_diff[1]**2)*100:.1f}%",
            'status': '좋음' if np.sqrt(position_diff[0]**2 + position_diff[1]**2) < 0.05 else '조정 필요'
        }

        # 압축감 피드백
        cam_type_map = {
            'normal': '표준',
            'wide': '광각',
            'telephoto': '망원',
            'normal_to_tele': '준망원'
        }

        feedback['compression'] = {
            'current': f"{cam_type_map.get(current.camera_type, current.camera_type)} ({current.compression_index:.2f})",
            'reference': f"{cam_type_map.get(reference.camera_type, reference.camera_type)} ({reference.compression_index:.2f})",
            'difference': f"{compression_diff:+.2f}",
            'status': '좋음' if abs(compression_diff) < 0.1 else '다른 렌즈 필요'
        }

        # 포즈 피드백
        pose_map = {
            'closeup': '클로즈업',
            'medium_shot': '미디엄샷',
            'knee_shot': '무릎샷',
            'full_shot': '전신샷'
        }

        feedback['pose'] = {
            'current': pose_map.get(current.pose_type, current.pose_type),
            'reference': pose_map.get(reference.pose_type, reference.pose_type),
            'match': current.pose_type == reference.pose_type
        }

        return feedback

    def _generate_visual_guides(self, current, reference, margin_diffs, position_diff):
        """시각적 가이드 정보 생성 (UI 오버레이용)"""

        guides = {
            'current_bbox': current.person_bbox,
            'reference_bbox': reference.person_bbox,
            'target_area': None,
            'movement_arrow': None,
            'grid_lines': None
        }

        # 목표 영역 계산
        if reference.person_bbox:
            x1, y1, x2, y2 = current.person_bbox
            width = x2 - x1
            height = y2 - y1

            # 레퍼런스 위치로 이동한 목표 영역
            target_x = reference.person_position[0] - width/2
            target_y = reference.person_position[1] - height/2
            guides['target_area'] = [
                target_x, target_y,
                target_x + width, target_y + height
            ]

        # 이동 방향 화살표
        if abs(position_diff[0]) > 0.05 or abs(position_diff[1]) > 0.05:
            guides['movement_arrow'] = {
                'start': current.person_position,
                'end': reference.person_position,
                'distance': np.sqrt(position_diff[0]**2 + position_diff[1]**2)
            }

        # Rule of Thirds 그리드
        guides['grid_lines'] = {
            'vertical': [0.33, 0.67],
            'horizontal': [0.33, 0.67]
        }

        return guides

    def _calculate_margins(self, bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """여백 계산"""
        x1, y1, x2, y2 = bbox
        return (y1, 1.0 - x2, 1.0 - y2, x1)  # top, right, bottom, left

    def _calculate_center(self, bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
        """중심점 계산"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def _detect_pose_type(self, bbox: Tuple[float, float, float, float]) -> str:
        """포즈 타입 감지"""
        x1, y1, x2, y2 = bbox
        bbox_height = y2 - y1

        if bbox_height < 0.3:
            return "closeup"
        elif bbox_height < 0.5:
            return "medium_shot"
        elif bbox_height < 0.7:
            return "knee_shot"
        else:
            return "full_shot"

    def _get_aspect_ratio(self, width: int, height: int) -> Tuple[str, str]:
        """종횡비 계산"""
        if width > height:
            orientation = "landscape"
            ratio = width / height
        elif height > width:
            orientation = "portrait"
            ratio = height / width
        else:
            orientation = "square"
            ratio = 1.0

        # 종횡비 판정
        if abs(ratio - 1.0) < 0.1:
            aspect_ratio = "1:1"
        elif abs(ratio - 1.33) < 0.1:
            aspect_ratio = "4:3"
        elif abs(ratio - 1.78) < 0.1:
            aspect_ratio = "16:9"
        else:
            if ratio < 1.5:
                aspect_ratio = "4:3"
            else:
                aspect_ratio = "16:9"

        return aspect_ratio, orientation


def print_comparison_result(result: ComparisonResult):
    """비교 결과를 보기 좋게 출력"""

    print("\n" + "="*60)
    print("비교 결과")
    print("="*60)

    # 유사도 점수
    print(f"\n유사도 점수: {result.similarity_score:.1f}/100")
    print(f"개선 가능 점수: {result.improvement_potential:.0f}/100")

    # 우선순위 액션
    if result.priority_actions:
        print("\n[우선순위 액션]")
        for action in result.priority_actions:
            print(f"\n   {action['priority']}. {action['action']} {action['direction']}")
            print(f"      이동량: {action['amount']}")
            print(f"      예상 효과: {action['impact']}")
    else:
        print("\n주요 조정사항이 없습니다!")

    # 상세 피드백
    print("\n[상세 분석]")

    margins = result.detailed_feedback.get('margins', {})
    if 'current' in margins:
        print(f"\n   여백:")
        print(f"      현재:     {margins.get('current', 'N/A')}")
        print(f"      레퍼런스: {margins.get('reference', 'N/A')}")
    print(f"      상태: {margins.get('status', 'N/A')}")

    print(f"\n   위치:")
    print(f"      현재:     {result.detailed_feedback['position']['current']}")
    print(f"      레퍼런스: {result.detailed_feedback['position']['reference']}")
    print(f"      거리: {result.detailed_feedback['position']['distance']}")

    print(f"\n   압축감:")
    print(f"      현재:     {result.detailed_feedback['compression']['current']}")
    print(f"      레퍼런스: {result.detailed_feedback['compression']['reference']}")
    print(f"      상태: {result.detailed_feedback['compression']['status']}")

    print("\n" + "="*60)


# ============================================================
# 메인 테스트 함수
# ============================================================

def main():
    """테스트 실행"""
    import argparse

    parser = argparse.ArgumentParser(description="Reference-based photo composition comparison")
    parser.add_argument("current", help="Path to current image")
    parser.add_argument("reference", help="Path to reference image")
    parser.add_argument("--mode", choices=['quick', 'detailed'], default='detailed',
                       help="Comparison mode")

    args = parser.parse_args()

    # 경로 확인
    if not Path(args.current).exists():
        print(f"Error: Current image not found: {args.current}")
        return

    if not Path(args.reference).exists():
        print(f"Error: Reference image not found: {args.reference}")
        return

    # 비교 실행
    comparator = ReferenceComparison()

    try:
        result = comparator.compare(
            args.current,
            args.reference,
            mode=args.mode
        )

        # 결과 출력
        print_comparison_result(result)

        # JSON으로 저장 (선택사항)
        output_path = Path("comparison_result.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False, default=str)
        print(f"\nResults saved to: {output_path}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()