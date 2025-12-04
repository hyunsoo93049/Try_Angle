#!/usr/bin/env python3
"""
TryAngle v1.5 - Smart Feedback v4
Gate System: 133개 키포인트 + 우선순위 기반 피드백
"""

import sys
import os
import time
import traceback
import math
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any
import json

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 경로 추가
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "legacy"))
sys.path.append(str(Path(__file__).parent.parent / "v1.5_learning"))

# RTMPose Wholebody Analyzer 임포트
from rtmpose_wholebody_analyzer import RTMPoseWholebodyAnalyzer

# Feedback Config 임포트
from feedback_config import FeedbackConfig, get_config, set_language

# Legacy 시스템 임포트 (v2 로직 활용)
from legacy.reference_comparison import (
    ReferenceComparison,
    ComparisonResult,
    ImageAnalysis
)

# 이미지 처리
try:
    from PIL import Image
except ImportError:
    import cv2


class SmartFeedbackV4:
    """
    Gate System: 133개 키포인트로 정확한 분석, 단계별 피드백
    """

    def __init__(self, language='ko'):
        """초기화"""
        print(f"[SmartFeedbackV4] 초기화 중... (언어: {language})")

        # 133개 키포인트 분석기
        self.wholebody = RTMPoseWholebodyAnalyzer(mode='balanced')

        # Legacy 시스템 (v2 압축감 로직)
        self.legacy_comparator = ReferenceComparison()

        # 언어 설정
        self.config = get_config(language)
        self.language = language

        # Gate 통과 기준
        self.gate_thresholds = {
            'framing': 70,     # 프레이밍 70% 이상 맞아야 다음 단계
            'composition': 75,  # 구도 75% 이상 맞아야 다음 단계
            'compression': 80   # 압축감 80% 이상 맞아야 포즈 체크
        }

        # 디바이스별 줌 시스템 (v2에서 가져옴)
        self.device_zoom_systems = {
            "iPhone": [0.5, 1.0, 2.0, 3.0, 5.0],
            "Galaxy": [0.6, 1.0, 3.0, 10.0],
            "generic": [0.5, 1.0, 2.0, 3.0, 5.0]
        }

        print("[SmartFeedbackV4] 초기화 완료")

    def analyze_with_gates(self, current_path: str, reference_path: str,
                          device_type: str = "generic") -> Dict[str, Any]:
        """
        Gate System 기반 분석

        Args:
            current_path: 현재 이미지 경로
            reference_path: 레퍼런스 이미지 경로
            device_type: 디바이스 타입

        Returns:
            단계별 피드백
        """
        print("\n[Gate System] 분석 시작")
        print("-" * 60)

        # 이미지 로드
        curr_img = self._load_image(current_path)
        ref_img = self._load_image(reference_path)

        if curr_img is None or ref_img is None:
            return {'error': '이미지 로드 실패'}

        # 133개 키포인트 추출 (한 번만)
        print("\n[1/2] 133개 키포인트 추출...")
        curr_kpts = self.wholebody.extract_wholebody_keypoints(curr_img)
        ref_kpts = self.wholebody.extract_wholebody_keypoints(ref_img)

        print(f"   현재: {curr_kpts['num_persons']}명 감지")
        print(f"   레퍼런스: {ref_kpts['num_persons']}명 감지")

        # Legacy 분석 (압축감용)
        print("\n[2/2] Legacy 시스템 분석...")
        legacy_result = self.legacy_comparator.compare(
            current_path=current_path,
            reference_path=reference_path,
            mode='detailed'
        )

        # Gate System 적용
        return self._apply_gate_system(
            curr_kpts, ref_kpts,
            curr_img.shape, ref_img.shape,
            legacy_result, device_type
        )

    def _apply_gate_system(self, curr_kpts: Dict, ref_kpts: Dict,
                          curr_shape: Tuple, ref_shape: Tuple,
                          legacy_result: Any, device_type: str) -> Dict[str, Any]:
        """
        Gate System 적용: 단계별 체크
        """

        # ============ GATE 1: 프레이밍 (최우선) ============
        print("\n[GATE 1] 프레이밍 체크...")
        framing_score, framing_feedback = self._check_framing(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        if framing_score < self.gate_thresholds['framing']:
            print(f"   [X] 프레이밍 불일치 (점수: {framing_score})")
            return {
                'status': 'FRAMING_MISMATCH',
                'gate_level': 1,
                'score': framing_score,
                'overall_score': framing_score,
                'critical_feedback': framing_feedback,
                'message': '먼저 화면에 담기는 범위를 조정하세요',
                'next_gates': []  # 다음 단계 없음
            }

        print(f"   [OK] 프레이밍 통과 (점수: {framing_score})")

        # ============ GATE 2: 구도 (프레이밍 통과시) ============
        print("\n[GATE 2] 구도 체크...")
        composition_score, composition_feedback = self._check_composition(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        if composition_score < self.gate_thresholds['composition']:
            print(f"   [X] 구도 조정 필요 (점수: {composition_score})")
            return {
                'status': 'COMPOSITION_ADJUST',
                'gate_level': 2,
                'score': composition_score,
                'overall_score': (framing_score + composition_score) / 2,
                'gates_passed': ['framing'],
                'critical_feedback': composition_feedback,
                'message': '인물 위치를 조정하세요',
                'next_gates': ['compression', 'pose']
            }

        print(f"   [OK] 구도 통과 (점수: {composition_score})")

        # ============ GATE 3: 압축감 (구도 통과시) ============
        print("\n[GATE 3] 압축감 체크...")
        compression_score, compression_feedback = self._check_compression(
            legacy_result, device_type
        )

        if compression_score < self.gate_thresholds['compression']:
            print(f"   [X] 압축감 조정 필요 (점수: {compression_score})")
            return {
                'status': 'COMPRESSION_ADJUST',
                'gate_level': 3,
                'score': compression_score,
                'overall_score': (framing_score + composition_score + compression_score) / 3,
                'gates_passed': ['framing', 'composition'],
                'critical_feedback': compression_feedback,
                'message': '배경 압축감을 조정하세요',
                'next_gates': ['pose']
            }

        print(f"   [OK] 압축감 통과 (점수: {compression_score})")

        # ============ GATE 4: 포즈 세부 (모두 통과시) ============
        print("\n[GATE 4] 포즈 세부 체크...")
        pose_feedback = self._check_pose_details(curr_kpts, ref_kpts)

        final_score = (framing_score + composition_score + compression_score) / 3

        if pose_feedback:
            final_score = min(95, final_score + 5)  # 포즈 맞으면 보너스

        return {
            'status': 'FINE_TUNING',
            'gate_level': 4,
            'score': final_score,
            'overall_score': final_score,
            'gates_passed': ['framing', 'composition', 'compression'],
            'optional_feedback': pose_feedback,
            'message': '기본기는 완벽! 세부 포즈만 조정하면 됩니다',
            'next_gates': []
        }

    def _check_framing(self, curr_kpts: Dict, ref_kpts: Dict,
                      curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """
        Gate 1: 프레이밍 체크 (샷 타입)
        """

        # 정밀한 샷 타입 판단 (133개 키포인트 활용)
        curr_shot = self._determine_shot_type_precise(curr_kpts)
        ref_shot = self._determine_shot_type_precise(ref_kpts)

        # 샷 타입이 같으면 높은 점수
        if curr_shot['type'] == ref_shot['type']:
            return 90, None

        # 다르면 조정 방법 계산
        adjustment = self._calculate_framing_adjustment(
            curr_shot, ref_shot, curr_shape[0]
        )

        # 점수는 차이 정도에 따라
        shot_order = ['extreme_closeup', 'closeup', 'bust_shot',
                     'medium_shot', 'knee_shot', 'full_shot']

        try:
            curr_idx = shot_order.index(curr_shot['type'])
            ref_idx = shot_order.index(ref_shot['type'])
            diff = abs(curr_idx - ref_idx)
            score = max(30, 70 - (diff * 15))  # 차이 클수록 점수 낮음
        except:
            score = 50

        feedback = {
            'issue': 'SHOT_TYPE_MISMATCH',
            'current': curr_shot,
            'target': ref_shot,
            'actions': adjustment['actions'],
            'visual_guide': adjustment.get('visual')
        }

        return score, feedback

    def _check_composition(self, curr_kpts: Dict, ref_kpts: Dict,
                          curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """
        Gate 2: 구도 체크 (인물 위치)
        """

        # 얼굴 중심점 계산 (68개 얼굴 랜드마크 활용)
        curr_center = self._calculate_face_center(curr_kpts, curr_shape)
        ref_center = self._calculate_face_center(ref_kpts, ref_shape)

        if curr_center is None or ref_center is None:
            return 75, None  # 얼굴 못 찾으면 기본 점수

        # 3분할 구도 위치
        curr_grid = self._to_grid_position(curr_center)
        ref_grid = self._to_grid_position(ref_center)

        # 같은 그리드면 높은 점수
        if curr_grid == ref_grid:
            return 90, None

        # 다르면 이동 거리 계산
        movement = self._calculate_movement(curr_center, ref_center, curr_shape)

        # 거리에 따른 점수
        distance = math.sqrt((curr_center[0] - ref_center[0])**2 +
                           (curr_center[1] - ref_center[1])**2)
        score = max(40, 80 - (distance * 100))  # 거리 멀수록 점수 낮음

        feedback = {
            'issue': 'POSITION_MISMATCH',
            'current_grid': curr_grid,
            'target_grid': ref_grid,
            'current_position': curr_center,
            'target_position': ref_center,
            'actions': movement['actions'],
            'visual_guide': self._generate_grid_visual(curr_grid, ref_grid)
        }

        return score, feedback

    def _check_compression(self, legacy_result: Any, device_type: str) -> Tuple[float, Optional[Dict]]:
        """
        Gate 3: 압축감 체크 (v2 로직 활용)
        """

        if not hasattr(legacy_result, 'detailed_feedback'):
            return 80, None

        if 'compression' not in legacy_result.detailed_feedback:
            return 80, None

        comp_data = legacy_result.detailed_feedback['compression']

        # 압축값 추출 (v2 스타일)
        import re
        curr_match = re.search(r'\(([0-9.]+)\)', comp_data.get('current', ''))
        ref_match = re.search(r'\(([0-9.]+)\)', comp_data.get('reference', ''))

        if not (curr_match and ref_match):
            return 80, None

        curr_comp = float(curr_match.group(1))
        ref_comp = float(ref_match.group(1))

        diff = abs(ref_comp - curr_comp)

        # 차이가 작으면 높은 점수
        if diff < 0.05:
            return 90, None

        # 줌 조정 계산 (v2 로직)
        zoom_adjustment = self._calculate_zoom_adjustment(curr_comp, ref_comp, device_type)

        # 차이에 따른 점수
        score = max(50, 85 - (diff * 100))

        feedback = {
            'issue': 'COMPRESSION_MISMATCH',
            'current_compression': curr_comp,
            'target_compression': ref_comp,
            'actions': zoom_adjustment['actions'],
            'zoom_info': zoom_adjustment
        }

        return score, feedback

    def _check_pose_details(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[List[Dict]]:
        """
        Gate 4: 포즈 세부 사항 (선택적)
        """

        minor_adjustments = []

        # 1. 손 제스처 체크 (42개 손 키포인트)
        if len(ref_kpts['right_hand']) > 15 or len(ref_kpts['left_hand']) > 15:
            hand_feedback = self._check_hand_gestures(curr_kpts, ref_kpts)
            if hand_feedback:
                minor_adjustments.append(hand_feedback)

        # 2. 얼굴 방향 체크 (68개 얼굴 랜드마크)
        if len(curr_kpts['face_landmarks']) > 30 and len(ref_kpts['face_landmarks']) > 30:
            face_feedback = self._check_face_direction(curr_kpts, ref_kpts)
            if face_feedback:
                minor_adjustments.append(face_feedback)

        # 3. 어깨 기울기 체크 (선택적)
        shoulder_feedback = self._check_shoulder_alignment(curr_kpts, ref_kpts)
        if shoulder_feedback:
            minor_adjustments.append(shoulder_feedback)

        return minor_adjustments if minor_adjustments else None

    # ================ Helper Functions ================

    def _load_image(self, path: str) -> Optional[np.ndarray]:
        """이미지 로드"""
        try:
            if 'PIL' in sys.modules:
                img = Image.open(path).convert('RGB')
                return np.array(img)
            else:
                img = cv2.imread(path)
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print(f"[ERROR] 이미지 로드 실패: {e}")
            return None

    def _determine_shot_type_precise(self, kpts: Dict) -> Dict[str, Any]:
        """133개 키포인트로 정밀한 샷 타입 판단"""

        if kpts['num_persons'] == 0:
            return {'type': 'unknown', 'confidence': 0}

        # 발 키포인트 체크 (최우선)
        if len(kpts['foot_keypoints']) >= 4:  # 6개 중 4개 이상
            return {
                'type': 'full_shot',
                'description': '전신샷',
                'confidence': 0.9
            }

        # 무릎 체크
        body = kpts['body_keypoints']
        if 'left_knee' in body or 'right_knee' in body:
            return {
                'type': 'knee_shot',
                'description': '무릎샷',
                'confidence': 0.85
            }

        # 엉덩이 체크
        if 'left_hip' in body and 'right_hip' in body:
            return {
                'type': 'medium_shot',
                'description': '미디엄샷',
                'confidence': 0.8
            }

        # 어깨만 보임
        if 'left_shoulder' in body and 'right_shoulder' in body:
            # 얼굴 랜드마크 많으면 바스트샷
            if len(kpts['face_landmarks']) > 50:
                return {
                    'type': 'bust_shot',
                    'description': '바스트샷',
                    'confidence': 0.75
                }
            else:
                return {
                    'type': 'closeup',
                    'description': '클로즈업',
                    'confidence': 0.7
                }

        # 얼굴만 보임
        if len(kpts['face_landmarks']) > 60:
            return {
                'type': 'extreme_closeup',
                'description': '익스트림 클로즈업',
                'confidence': 0.8
            }

        return {'type': 'unknown', 'confidence': 0.3}

    def _calculate_framing_adjustment(self, curr_shot: Dict, ref_shot: Dict,
                                     img_height: int) -> Dict[str, Any]:
        """프레이밍 조정 방법 계산"""

        shot_order = ['extreme_closeup', 'closeup', 'bust_shot',
                     'medium_shot', 'knee_shot', 'full_shot']

        try:
            curr_idx = shot_order.index(curr_shot['type'])
            ref_idx = shot_order.index(ref_shot['type'])
        except:
            return {'actions': ['샷 타입을 조정하세요']}

        actions = []

        if curr_idx < ref_idx:  # 더 넓게
            steps = ref_idx - curr_idx
            distance = steps * 30  # 단계당 30cm
            zoom = 0.7 ** steps  # 단계당 0.7배

            actions.append(f"카메라를 뒤로 {distance}cm 이동")
            actions.append(f"또는 줌을 {zoom:.1f}배로 축소")

            direction = 'wider'
        else:  # 더 좁게
            steps = curr_idx - ref_idx
            distance = steps * 30
            zoom = 1.4 ** steps  # 단계당 1.4배

            actions.append(f"카메라를 앞으로 {distance}cm 이동")
            actions.append(f"또는 줌을 {zoom:.1f}배로 확대")

            direction = 'tighter'

        return {
            'actions': actions,
            'direction': direction,
            'steps': steps
        }

    def _calculate_face_center(self, kpts: Dict, img_shape: Tuple) -> Optional[Tuple[float, float]]:
        """얼굴 중심 계산 (68개 랜드마크 평균)"""

        if kpts['num_persons'] == 0:
            return None

        face = kpts.get('face_landmarks', {})

        # 얼굴 랜드마크가 충분히 있으면
        if len(face) > 30:
            positions = [kpt['position'] for kpt in face.values()]
            avg_x = np.mean([p[0] for p in positions]) / img_shape[1]
            avg_y = np.mean([p[1] for p in positions]) / img_shape[0]
            return (avg_x, avg_y)

        # 없으면 코 위치 사용
        if 'nose' in kpts.get('body_keypoints', {}):
            nose = kpts['body_keypoints']['nose']['position']
            return (nose[0] / img_shape[1], nose[1] / img_shape[0])

        return None

    def _to_grid_position(self, pos: Tuple[float, float]) -> Tuple[int, int]:
        """3분할 구도 위치 변환"""
        grid_x = min(int(pos[0] * 3) + 1, 3)
        grid_y = min(int(pos[1] * 3) + 1, 3)
        return (grid_x, grid_y)

    def _calculate_movement(self, curr_pos: Tuple, ref_pos: Tuple,
                           img_shape: Tuple) -> Dict[str, Any]:
        """이동 거리 계산 (cm 단위)"""

        # 스마트폰 화면 약 15cm 가정
        screen_width_cm = 15
        pixel_to_cm = screen_width_cm / img_shape[1]

        x_diff = (ref_pos[0] - curr_pos[0]) * img_shape[1] * pixel_to_cm
        y_diff = (ref_pos[1] - curr_pos[1]) * img_shape[0] * pixel_to_cm

        actions = []

        if abs(x_diff) > 1:  # 1cm 이상 차이
            direction = "오른쪽" if x_diff > 0 else "왼쪽"
            actions.append(f"인물을 {direction}으로 {abs(x_diff):.1f}cm 이동")

        if abs(y_diff) > 1:
            direction = "아래" if y_diff > 0 else "위"
            actions.append(f"인물을 {direction}로 {abs(y_diff):.1f}cm 이동")

        return {'actions': actions, 'distance_cm': math.sqrt(x_diff**2 + y_diff**2)}

    def _generate_grid_visual(self, curr_grid: Tuple, ref_grid: Tuple) -> str:
        """3분할 구도 시각화"""

        grid_visual = "+---+---+---+\n"

        for y in range(1, 4):
            row = "|"
            for x in range(1, 4):
                if (x, y) == ref_grid:
                    row += " * |"  # 목표
                elif (x, y) == curr_grid:
                    row += " o |"  # 현재
                else:
                    row += "   |"
            grid_visual += row + "\n"
            if y < 3:
                grid_visual += "+---+---+---+\n"

        grid_visual += "+---+---+---+"
        grid_visual += "\no = 현재, * = 목표"

        return grid_visual

    def _calculate_zoom_adjustment(self, curr_comp: float, ref_comp: float,
                                  device_type: str) -> Dict[str, Any]:
        """압축감 조정 방향 계산 (상대적 비교)"""

        diff = ref_comp - curr_comp
        actions = []

        # 압축감 구간 설명
        def describe_compression(value):
            if value < 0.3:
                return "광각 느낌"
            elif value < 0.5:
                return "표준 느낌"
            elif value < 0.7:
                return "약간의 압축감"
            else:
                return "망원 느낌"

        if abs(diff) < 0.05:
            # 거의 같음
            actions.append("압축감이 적절합니다")
        elif curr_comp < ref_comp:
            # 현재가 더 광각 -> 압축감 늘려야 함
            intensity = "조금" if abs(diff) < 0.2 else "좀 더"
            actions.append(f"피사체에 {intensity} 가까이 가세요")
            actions.append(f"또는 줌을 {intensity} 확대하세요")

            # 거리 추정
            if abs(diff) < 0.15:
                actions.append("(예상: 한두 걸음)")
            elif abs(diff) < 0.3:
                actions.append("(예상: 서너 걸음)")
            else:
                actions.append("(예상: 상당한 거리)")
        else:
            # 현재가 더 망원 -> 압축감 줄여야 함
            intensity = "조금" if abs(diff) < 0.2 else "좀 더"
            actions.append(f"피사체에서 {intensity} 멀어지세요")
            actions.append(f"또는 줌을 {intensity} 축소하세요")

            # 거리 추정
            if abs(diff) < 0.15:
                actions.append("(예상: 한두 걸음)")
            elif abs(diff) < 0.3:
                actions.append("(예상: 서너 걸음)")
            else:
                actions.append("(예상: 상당한 거리)")

        return {
            'actions': actions,
            'current_desc': describe_compression(curr_comp),
            'target_desc': describe_compression(ref_comp),
            'current_value': curr_comp,
            'target_value': ref_comp
        }

    def _check_hand_gestures(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[Dict]:
        """손 제스처 체크"""

        # 간단한 제스처 감지 (손 키포인트 개수로 판단)
        curr_right = len(curr_kpts.get('right_hand', {}))
        ref_right = len(ref_kpts.get('right_hand', {}))

        if ref_right > 15 and curr_right < 10:
            return {
                'category': 'hand',
                'importance': 'optional',
                'suggestion': '손 제스처가 보이도록 손을 들어주세요'
            }

        return None

    def _check_face_direction(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[Dict]:
        """얼굴 방향 체크"""

        # 간단히 얼굴 랜드마크 분포로 판단
        curr_face = curr_kpts.get('face_landmarks', {})
        ref_face = ref_kpts.get('face_landmarks', {})

        if len(curr_face) < 30 or len(ref_face) < 30:
            return None

        # 좌우 랜드마크 개수 차이로 방향 추정
        # (실제로는 더 정교한 로직 필요)

        return None  # 일단 생략

    def _check_shoulder_alignment(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[Dict]:
        """어깨 정렬 체크"""

        curr_body = curr_kpts.get('body_keypoints', {})
        ref_body = ref_kpts.get('body_keypoints', {})

        # 어깨 둘 다 있는지 체크
        if not all(k in curr_body for k in ['left_shoulder', 'right_shoulder']):
            return None
        if not all(k in ref_body for k in ['left_shoulder', 'right_shoulder']):
            return None

        # 어깨 기울기 계산
        curr_left = curr_body['left_shoulder']['position']
        curr_right = curr_body['right_shoulder']['position']

        curr_tilt = math.degrees(math.atan2(
            curr_right[1] - curr_left[1],
            curr_right[0] - curr_left[0]
        ))

        # 수평에서 벗어난 정도
        if abs(curr_tilt) > 5:
            return {
                'category': 'posture',
                'importance': 'optional',
                'suggestion': f"어깨를 수평으로 맞춰주세요 (현재 {abs(curr_tilt):.1f}도 기울어짐)"
            }

        return None


def print_smart_feedback(result: Dict, language: str = 'ko'):
    """Gate System 피드백 출력"""

    print("\n" + "="*70)
    print("[TryAngle v4] Smart Feedback System")
    print("="*70)

    # 전체 점수
    print(f"\n[전체 점수] {result.get('overall_score', 0):.0f}/100")

    # Gate 레벨별 상태
    gate_level = result.get('gate_level', 0)
    status = result.get('status', 'UNKNOWN')

    print(f"\n[현재 상태] Gate {gate_level} - {status}")

    # 통과한 Gate들
    passed = result.get('gates_passed', [])
    if passed:
        print(f"\n[OK] 통과한 단계:")
        for gate in passed:
            if gate == 'framing':
                print("   - 프레이밍 (화면 범위)")
            elif gate == 'composition':
                print("   - 구도 (인물 위치)")
            elif gate == 'compression':
                print("   - 압축감 (배경 깊이)")

    # 현재 문제점과 해결 방법
    if result.get('critical_feedback'):
        feedback = result['critical_feedback']

        print(f"\n[!] [우선 해결 필요]")
        print("-" * 60)

        if feedback.get('current'):
            print(f"현재: {feedback['current'].get('description', '')}")
        if feedback.get('target'):
            print(f"목표: {feedback['target'].get('description', '')}")

        if feedback.get('actions'):
            print(f"\n[즉시 실행]")
            for i, action in enumerate(feedback['actions'], 1):
                print(f"  {i}. {action}")

        # 시각적 가이드
        if feedback.get('visual_guide'):
            print(f"\n[시각적 가이드]")
            print(feedback['visual_guide'])

        print("\n[!] 이것을 먼저 해결한 후 다시 촬영하세요!")

    # 선택적 피드백 (모든 기본 통과시)
    elif result.get('optional_feedback'):
        print(f"\n[*] [기본기 완벽! 선택적 미세조정]")
        print("-" * 60)

        for item in result['optional_feedback']:
            print(f"\n- {item.get('suggestion', '')}")
            print(f"  (중요도: {item.get('importance', 'optional')})")

        print("\n[100] 이미 충분히 좋습니다! 위 사항은 선택사항입니다.")

    # 다음 단계 예고
    next_gates = result.get('next_gates', [])
    if next_gates:
        print(f"\n[다음 체크 항목]")
        for gate in next_gates:
            if gate == 'compression':
                print("  - 압축감 (배경 깊이)")
            elif gate == 'pose':
                print("  - 포즈 세부사항")

    print("\n" + "="*70)


def main():
    """메인 실행 함수"""

    try:
        print("\n" + "="*70)
        print("  TryAngle v4 - Smart Feedback System  ")
        print("  (Gate System: 우선순위 기반 피드백)  ")
        print("="*70)

        # 언어 선택
        print("\n[Language / 언어]")
        print("  1. 한국어 (Korean)")
        print("  2. English")
        lang_choice = input("선택 (1-2, 기본=1): ").strip()

        language = 'ko' if lang_choice != '2' else 'en'

        # 시스템 초기화
        feedback_system = SmartFeedbackV4(language=language)

        # 이미지 입력
        print("\n[이미지 입력]")
        print("-" * 40)

        current_path = input("현재 이미지 경로: ").strip().replace('"', '').replace("'", '')
        if not Path(current_path).exists():
            print(f"파일을 찾을 수 없습니다: {current_path}")
            return

        reference_path = input("레퍼런스 이미지 경로: ").strip().replace('"', '').replace("'", '')
        if not Path(reference_path).exists():
            print(f"파일을 찾을 수 없습니다: {reference_path}")
            return

        # 디바이스 선택
        print("\n[디바이스 선택] (Enter로 건너뛰기)")
        print("  1. iPhone")
        print("  2. Galaxy")
        print("  3. 기타")
        device_choice = input("선택: ").strip()

        device_type = "generic"
        if device_choice == "1":
            device_type = "iPhone"
        elif device_choice == "2":
            device_type = "Galaxy"

        # 분석 실행
        print("\n[처리 중...]")
        print("-" * 40)

        start_time = time.time()

        result = feedback_system.analyze_with_gates(
            current_path=current_path,
            reference_path=reference_path,
            device_type=device_type
        )

        total_time = time.time() - start_time

        # 결과 출력
        print_smart_feedback(result, language)

        print(f"\n분석 시간: {total_time:.1f}초")

        # 재실행
        print("\n" + "="*70)
        again = input("\n다른 이미지를 비교하시겠습니까? (y/n): ").lower()
        if again == 'y':
            main()
        else:
            print("\nTryAngle v4를 이용해 주셔서 감사합니다!")

    except KeyboardInterrupt:
        print("\n\n종료합니다...")
    except Exception as e:
        print(f"\n오류: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()