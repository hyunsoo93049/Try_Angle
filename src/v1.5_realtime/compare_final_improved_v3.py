#!/usr/bin/env python3
"""
TryAngle v1.5 - Enhanced Image Comparison with 133 Keypoints
RTMPose Wholebody 기반 정밀 분석 시스템
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

# Legacy 시스템 임포트
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


class ImprovedFeedbackV3:
    """133개 키포인트 기반 향상된 피드백 생성기"""

    def __init__(self):
        """초기화"""
        print("[ImprovedFeedbackV3] 초기화 중...")

        # RTMPose Wholebody 분석기
        self.pose_analyzer = RTMPoseWholebodyAnalyzer(mode='balanced')

        # Legacy 비교 시스템
        self.legacy_comparator = ReferenceComparison()

        # 디바이스별 줌 시스템
        self.device_zoom_systems = {
            "iPhone": [0.5, 1.0, 2.0, 3.0, 5.0],
            "Galaxy": [0.6, 1.0, 3.0, 10.0],
            "generic": [0.5, 1.0, 2.0, 3.0, 5.0]
        }

        print("[ImprovedFeedbackV3] 초기화 완료")

    def compare_with_keypoints(self, current_path: str, reference_path: str,
                               device_type: str = "generic") -> Dict[str, Any]:
        """
        133개 키포인트 기반 이미지 비교

        Args:
            current_path: 현재 이미지 경로
            reference_path: 레퍼런스 이미지 경로
            device_type: 기기 타입

        Returns:
            비교 결과 및 피드백
        """
        print("\n[분석 시작] 133개 키포인트 기반 비교")
        print("-" * 60)

        # 이미지 로드
        curr_img = self._load_image(current_path)
        ref_img = self._load_image(reference_path)

        if curr_img is None or ref_img is None:
            return {'error': '이미지 로드 실패'}

        # 1. Legacy 시스템으로 기본 비교 (압축감, 색상 등)
        print("\n[1/4] Legacy 시스템 분석...")
        legacy_result = self.legacy_comparator.compare(
            current_path=current_path,
            reference_path=reference_path,
            mode='detailed'
        )

        # 2. 133개 키포인트 추출
        print("\n[2/4] Wholebody 키포인트 추출...")
        curr_kpts = self.pose_analyzer.extract_wholebody_keypoints(curr_img)
        ref_kpts = self.pose_analyzer.extract_wholebody_keypoints(ref_img)

        print(f"   현재: {curr_kpts['num_persons']}명 감지")
        print(f"   레퍼런스: {ref_kpts['num_persons']}명 감지")

        # 3. 키포인트 기반 정밀 분석
        print("\n[3/4] 정밀 포즈 분석...")
        pose_analysis = self._analyze_pose_differences(
            curr_kpts, ref_kpts, curr_img.shape, ref_img.shape
        )

        # 4. 통합 피드백 생성
        print("\n[4/4] 피드백 생성...")
        feedback = self._generate_enhanced_feedback(
            legacy_result, pose_analysis, curr_kpts, ref_kpts, device_type
        )

        return {
            'legacy_score': legacy_result.similarity_score,
            'pose_analysis': pose_analysis,
            'feedback': feedback,
            'keypoint_stats': {
                'current': {
                    'body': len(curr_kpts['body_keypoints']),
                    'face': len(curr_kpts['face_landmarks']),
                    'hands': len(curr_kpts['left_hand']) + len(curr_kpts['right_hand']),
                    'feet': len(curr_kpts['foot_keypoints'])
                },
                'reference': {
                    'body': len(ref_kpts['body_keypoints']),
                    'face': len(ref_kpts['face_landmarks']),
                    'hands': len(ref_kpts['left_hand']) + len(ref_kpts['right_hand']),
                    'feet': len(ref_kpts['foot_keypoints'])
                }
            }
        }

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

    def _analyze_pose_differences(self, curr_kpts: Dict, ref_kpts: Dict,
                                 curr_shape: Tuple, ref_shape: Tuple) -> Dict[str, Any]:
        """포즈 차이 정밀 분석"""

        analysis = {
            'shot_type': {},
            'body_posture': {},
            'face_direction': {},
            'hand_gestures': {},
            'composition': {}
        }

        # 샷 타입 비교
        curr_shot = self.pose_analyzer.get_enhanced_shot_type(curr_kpts, curr_shape[0])
        ref_shot = self.pose_analyzer.get_enhanced_shot_type(ref_kpts, ref_shape[0])

        analysis['shot_type'] = {
            'current': curr_shot,
            'reference': ref_shot,
            'match': curr_shot['type'] == ref_shot['type'],
            'adjustment_needed': self._get_shot_adjustment(curr_shot['type'], ref_shot['type'])
        }

        # 자세 비교
        if curr_kpts['num_persons'] > 0 and ref_kpts['num_persons'] > 0:
            curr_posture = self.pose_analyzer.analyze_body_posture(curr_kpts)
            ref_posture = self.pose_analyzer.analyze_body_posture(ref_kpts)

            analysis['body_posture'] = {
                'current': curr_posture,
                'reference': ref_posture,
                'differences': self._compare_postures(curr_posture, ref_posture)
            }

        # 얼굴 방향 비교
        if len(curr_kpts['face_landmarks']) > 30 and len(ref_kpts['face_landmarks']) > 30:
            curr_face = self.pose_analyzer.analyze_face_direction(curr_kpts['face_landmarks'])
            ref_face = self.pose_analyzer.analyze_face_direction(ref_kpts['face_landmarks'])

            analysis['face_direction'] = {
                'current': curr_face,
                'reference': ref_face,
                'match': self._compare_face_directions(curr_face, ref_face)
            }

        # 손 제스처 비교
        if len(curr_kpts['right_hand']) > 10 or len(curr_kpts['left_hand']) > 10:
            curr_hands = {
                'left': self.pose_analyzer.analyze_hand_gesture(curr_kpts['left_hand'], 'left') if len(curr_kpts['left_hand']) > 10 else None,
                'right': self.pose_analyzer.analyze_hand_gesture(curr_kpts['right_hand'], 'right') if len(curr_kpts['right_hand']) > 10 else None
            }
            ref_hands = {
                'left': self.pose_analyzer.analyze_hand_gesture(ref_kpts['left_hand'], 'left') if len(ref_kpts['left_hand']) > 10 else None,
                'right': self.pose_analyzer.analyze_hand_gesture(ref_kpts['right_hand'], 'right') if len(ref_kpts['right_hand']) > 10 else None
            }

            analysis['hand_gestures'] = {
                'current': curr_hands,
                'reference': ref_hands,
                'match': self._compare_hand_gestures(curr_hands, ref_hands)
            }

        # 구도 분석
        analysis['composition'] = self._analyze_composition_differences(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        return analysis

    def _get_shot_adjustment(self, current_type: str, target_type: str) -> Dict[str, Any]:
        """샷 타입 조정 방법"""

        if current_type == target_type:
            return {'needed': False, 'message': '샷 타입 일치'}

        shot_order = [
            'extreme_closeup', 'closeup', 'bust_shot',
            'medium_shot', 'knee_shot', 'full_shot', 'long_shot'
        ]

        try:
            curr_idx = shot_order.index(current_type)
            ref_idx = shot_order.index(target_type)
        except ValueError:
            return {'needed': True, 'message': '샷 타입 조정 필요'}

        if curr_idx < ref_idx:  # 더 넓게
            steps = ref_idx - curr_idx
            return {
                'needed': True,
                'direction': 'wider',
                'steps': steps,
                'methods': [
                    f"카메라를 뒤로 {steps * 30}cm 이동",
                    f"줌을 {steps * 0.3:.1f}배 축소",
                    "더 많은 신체 부위가 포함되도록 조정"
                ]
            }
        else:  # 더 좁게
            steps = curr_idx - ref_idx
            return {
                'needed': True,
                'direction': 'tighter',
                'steps': steps,
                'methods': [
                    f"카메라를 앞으로 {steps * 30}cm 이동",
                    f"줌을 {steps * 0.3:.1f}배 확대",
                    "특정 부위에 집중하도록 조정"
                ]
            }

    def _compare_postures(self, curr: Dict, ref: Dict) -> List[Dict]:
        """자세 차이점 비교"""
        differences = []

        # 어깨 정렬 비교
        if 'shoulder_alignment' in curr and 'shoulder_alignment' in ref:
            curr_angle = curr['shoulder_alignment'].get('angle', 0)
            ref_angle = ref['shoulder_alignment'].get('angle', 0)
            diff = abs(curr_angle - ref_angle)

            if diff > 5:
                differences.append({
                    'type': 'shoulder_alignment',
                    'current': curr_angle,
                    'target': ref_angle,
                    'difference': diff,
                    'action': curr['shoulder_alignment'].get('adjustment', '')
                })

        # 골반 정렬 비교
        if 'hip_alignment' in curr and 'hip_alignment' in ref:
            curr_balance = curr['hip_alignment'].get('balance', False)
            ref_balance = ref['hip_alignment'].get('balance', False)

            if curr_balance != ref_balance and ref_balance:
                differences.append({
                    'type': 'hip_balance',
                    'current': '불균형' if not curr_balance else '균형',
                    'target': '균형',
                    'action': '골반을 수평으로 맞추기'
                })

        # 스탠스 비교
        if 'stance' in curr and 'stance' in ref:
            curr_width = curr['stance'].get('width', 0)
            ref_width = ref['stance'].get('width', 0)
            width_diff = abs(curr_width - ref_width)

            if width_diff > 50:  # 50픽셀 이상 차이
                differences.append({
                    'type': 'stance_width',
                    'current': curr['stance'].get('type', ''),
                    'target': ref['stance'].get('type', ''),
                    'action': f"발을 {'더 벌리기' if curr_width < ref_width else '더 모으기'}"
                })

        return differences

    def _compare_face_directions(self, curr: Dict, ref: Dict) -> bool:
        """얼굴 방향 일치 여부"""
        if not curr or not ref:
            return False

        # 수평 회전 비교
        curr_rotation = curr.get('horizontal_rotation', {}).get('offset_ratio', 0)
        ref_rotation = ref.get('horizontal_rotation', {}).get('offset_ratio', 0)

        return abs(curr_rotation - ref_rotation) < 15  # 15% 이내 차이

    def _compare_hand_gestures(self, curr: Dict, ref: Dict) -> bool:
        """손 제스처 일치 여부"""
        left_match = False
        right_match = False

        if curr['left'] and ref['left']:
            left_match = curr['left'].get('gesture') == ref['left'].get('gesture')

        if curr['right'] and ref['right']:
            right_match = curr['right'].get('gesture') == ref['right'].get('gesture')

        return left_match or right_match

    def _analyze_composition_differences(self, curr_kpts: Dict, ref_kpts: Dict,
                                        curr_shape: Tuple, ref_shape: Tuple) -> Dict:
        """구도 차이 분석"""

        composition = {'differences': []}

        # 얼굴 위치 비교 (코 기준)
        if curr_kpts['num_persons'] > 0 and ref_kpts['num_persons'] > 0:
            curr_kp = curr_kpts['keypoints'][0]
            ref_kp = ref_kpts['keypoints'][0]

            # 코 위치 (인덱스 0)
            if curr_kpts['scores'][0][0] > 0.5 and ref_kpts['scores'][0][0] > 0.5:
                curr_nose = (curr_kp[0][0] / curr_shape[1], curr_kp[0][1] / curr_shape[0])
                ref_nose = (ref_kp[0][0] / ref_shape[1], ref_kp[0][1] / ref_shape[0])

                x_diff = (ref_nose[0] - curr_nose[0]) * 100
                y_diff = (ref_nose[1] - curr_nose[1]) * 100

                if abs(x_diff) > 5:  # 5% 이상 차이
                    composition['differences'].append({
                        'type': 'horizontal_position',
                        'current': curr_nose[0],
                        'target': ref_nose[0],
                        'adjustment': f"{'왼쪽' if x_diff < 0 else '오른쪽'}으로 {abs(x_diff):.0f}% 이동"
                    })

                if abs(y_diff) > 5:
                    composition['differences'].append({
                        'type': 'vertical_position',
                        'current': curr_nose[1],
                        'target': ref_nose[1],
                        'adjustment': f"{'위' if y_diff < 0 else '아래'}로 {abs(y_diff):.0f}% 이동"
                    })

        return composition

    def _generate_enhanced_feedback(self, legacy_result: ComparisonResult,
                                   pose_analysis: Dict, curr_kpts: Dict,
                                   ref_kpts: Dict, device_type: str) -> Dict[str, Any]:
        """향상된 피드백 생성"""

        feedback = {
            'overall_score': legacy_result.similarity_score,
            'improvement_potential': legacy_result.improvement_potential,
            'priority_actions': [],
            'detailed_guidance': {}
        }

        # 우선순위 액션 생성
        priority = 1

        # 1. 샷 타입 조정
        if not pose_analysis['shot_type']['match']:
            adjustment = pose_analysis['shot_type']['adjustment_needed']
            if adjustment['needed']:
                feedback['priority_actions'].append({
                    'priority': priority,
                    'category': '구도',
                    'action': '샷 타입 조정',
                    'current': pose_analysis['shot_type']['current']['description'],
                    'target': pose_analysis['shot_type']['reference']['description'],
                    'methods': adjustment['methods'],
                    'impact': '높음'
                })
                priority += 1

        # 2. 자세 조정
        if 'differences' in pose_analysis['body_posture']:
            for diff in pose_analysis['body_posture']['differences'][:2]:  # 상위 2개만
                feedback['priority_actions'].append({
                    'priority': priority,
                    'category': '자세',
                    'action': diff['type'].replace('_', ' ').title(),
                    'current': diff.get('current', ''),
                    'target': diff.get('target', ''),
                    'adjustment': diff.get('action', ''),
                    'impact': '중간'
                })
                priority += 1

        # 3. 얼굴 방향 조정
        if 'face_direction' in pose_analysis and not pose_analysis['face_direction'].get('match', True):
            curr_face = pose_analysis['face_direction'].get('current', {})
            ref_face = pose_analysis['face_direction'].get('reference', {})

            if curr_face and ref_face:
                feedback['priority_actions'].append({
                    'priority': priority,
                    'category': '얼굴',
                    'action': '시선 방향 조정',
                    'current': curr_face.get('horizontal_rotation', {}).get('direction', '정면'),
                    'target': ref_face.get('horizontal_rotation', {}).get('direction', '정면'),
                    'adjustment': '레퍼런스와 동일한 방향으로 얼굴 회전',
                    'impact': '중간'
                })
                priority += 1

        # 4. 손 제스처 조정
        if 'hand_gestures' in pose_analysis and not pose_analysis['hand_gestures'].get('match', True):
            curr_hands = pose_analysis['hand_gestures'].get('current', {})
            ref_hands = pose_analysis['hand_gestures'].get('reference', {})

            if ref_hands.get('right') and ref_hands['right']:
                target_gesture = ref_hands['right'].get('gesture', 'unknown')
                current_gesture = curr_hands.get('right', {}).get('gesture', 'none') if curr_hands.get('right') else 'none'

                if target_gesture != 'unknown' and current_gesture != target_gesture:
                    feedback['priority_actions'].append({
                        'priority': priority,
                        'category': '제스처',
                        'action': '손 모양 조정',
                        'current': current_gesture,
                        'target': target_gesture,
                        'adjustment': f"오른손을 {self._describe_gesture(target_gesture)} 모양으로",
                        'impact': '낮음'
                    })
                    priority += 1

        # 5. 구도 미세 조정
        if 'composition' in pose_analysis:
            for comp_diff in pose_analysis['composition'].get('differences', [])[:1]:  # 상위 1개
                feedback['priority_actions'].append({
                    'priority': priority,
                    'category': '위치',
                    'action': '인물 위치 조정',
                    'adjustment': comp_diff.get('adjustment', ''),
                    'impact': '낮음'
                })
                priority += 1

        # 상세 가이드 추가
        feedback['detailed_guidance'] = {
            'shot_type': self._get_shot_type_guide(pose_analysis),
            'body_posture': self._get_posture_guide(pose_analysis),
            'facial_expression': self._get_facial_guide(curr_kpts, ref_kpts),
            'technical_settings': self._get_technical_guide(legacy_result, device_type)
        }

        return feedback

    def _describe_gesture(self, gesture: str) -> str:
        """제스처 설명"""
        gestures = {
            'open_palm': '손바닥 펴기',
            'fist': '주먹',
            'pointing': '가리키기',
            'thumbs_up': '엄지 올리기',
            'peace': '브이',
            '2_fingers': '두 손가락',
            '3_fingers': '세 손가락'
        }
        return gestures.get(gesture, gesture)

    def _get_shot_type_guide(self, analysis: Dict) -> Dict:
        """샷 타입 가이드"""
        if not analysis.get('shot_type'):
            return {}

        curr = analysis['shot_type'].get('current', {})
        ref = analysis['shot_type'].get('reference', {})
        adjustment = analysis['shot_type'].get('adjustment_needed', {})

        return {
            'current_coverage': f"{curr.get('coverage', 0) * 100:.0f}%",
            'target_coverage': f"{ref.get('coverage', 0) * 100:.0f}%",
            'face_detail_needed': ref.get('face_landmarks_count', 0) > 50,
            'hands_visible_needed': ref.get('hand_keypoints_count', 0) > 20,
            'adjustment_steps': adjustment.get('methods', [])
        }

    def _get_posture_guide(self, analysis: Dict) -> Dict:
        """자세 가이드"""
        if not analysis.get('body_posture'):
            return {}

        curr = analysis['body_posture'].get('current', {})
        differences = analysis['body_posture'].get('differences', [])

        guide = {
            'issues_count': len(differences),
            'corrections': []
        }

        for diff in differences:
            guide['corrections'].append({
                'issue': diff['type'],
                'action': diff.get('action', ''),
                'importance': 'high' if diff['type'] == 'shoulder_alignment' else 'medium'
            })

        return guide

    def _get_facial_guide(self, curr_kpts: Dict, ref_kpts: Dict) -> Dict:
        """표정 가이드"""
        guide = {}

        curr_face_count = len(curr_kpts.get('face_landmarks', {}))
        ref_face_count = len(ref_kpts.get('face_landmarks', {}))

        if ref_face_count > 50:
            guide['detail_level'] = 'high'
            guide['expression_visible'] = True

            if curr_face_count < 30:
                guide['adjustment'] = '얼굴이 더 선명히 보이도록 가까이 또는 조명 개선'
        else:
            guide['detail_level'] = 'low'
            guide['expression_visible'] = False

        return guide

    def _get_technical_guide(self, legacy_result: ComparisonResult, device_type: str) -> Dict:
        """기술적 설정 가이드"""
        guide = {
            'device_type': device_type,
            'recommended_zoom': '1.0x'
        }

        # Legacy 결과에서 압축감 정보 추출
        if hasattr(legacy_result, 'detailed_feedback'):
            if 'compression' in legacy_result.detailed_feedback:
                comp_info = legacy_result.detailed_feedback['compression']
                # 압축감에 따른 줌 추천
                guide['compression_adjustment'] = comp_info

        return guide


def print_enhanced_feedback_v3(result: Dict, device_type: str = "generic", language: str = 'ko'):
    """향상된 피드백 v3 출력"""

    # 설정 가져오기
    config = get_config(language)

    print("\n" + "="*70)
    print(config.get('headers.main_title'))
    print("="*70)

    # 기본 점수
    feedback = result.get('feedback', {})
    print(f"\n{config.get('headers.overall_score')} {feedback.get('overall_score', 0):.0f}/100{config.get('labels.points')}")
    print(f"{config.get('headers.improvement_potential')} +{feedback.get('improvement_potential', 0):.0f}{config.get('labels.points')}")

    # 키포인트 통계
    stats = result.get('keypoint_stats', {})
    if stats:
        print(f"\n{config.get('headers.keypoint_detection')}")
        print(f"  {config.get('keypoints.current')}:   "
              f"{config.get('keypoints.body')} {stats['current']['body']}/17 | "
              f"{config.get('keypoints.face')} {stats['current']['face']}/68 | "
              f"{config.get('keypoints.hands')} {stats['current']['hands']}/42 | "
              f"{config.get('keypoints.feet')} {stats['current']['feet']}/6")
        print(f"  {config.get('keypoints.reference')}:    "
              f"{config.get('keypoints.body')} {stats['reference']['body']}/17 | "
              f"{config.get('keypoints.face')} {stats['reference']['face']}/68 | "
              f"{config.get('keypoints.hands')} {stats['reference']['hands']}/42 | "
              f"{config.get('keypoints.feet')} {stats['reference']['feet']}/6")

    # 우선순위 액션
    priority_actions = feedback.get('priority_actions', [])
    if priority_actions:
        print(f"\n[우선순위별 조정사항] ({len(priority_actions)}개)")
        print("-" * 70)

        for action in priority_actions[:5]:  # 상위 5개만
            print(f"\n{action['priority']}. [{action['category']}] {action['action']}")

            if 'current' in action and action['current']:
                print(f"   현재: {action['current']}")
            if 'target' in action and action['target']:
                print(f"   목표: {action['target']}")

            if 'adjustment' in action:
                print(f"   -> {action['adjustment']}")

            if 'methods' in action:
                for method in action['methods']:
                    print(f"     - {method}")

            impact_kr = {'높음': '높음', '중간': '보통', '낮음': '낮음'}
            print(f"   중요도: {impact_kr.get(action.get('impact', ''), action.get('impact', '알수없음'))}")

    # 상세 가이드
    detailed = feedback.get('detailed_guidance', {})
    if detailed:
        print("\n[상세 가이드]")
        print("-" * 70)

        # 샷 타입 가이드
        if 'shot_type' in detailed and detailed['shot_type']:
            shot = detailed['shot_type']
            print(f"\n- 샷 타입:")
            print(f"  화면 차지 비율: {shot.get('current_coverage', '알수없음')} -> {shot.get('target_coverage', '알수없음')}")
            if shot.get('face_detail_needed'):
                print(f"  [!] 얼굴 디테일이 선명하게 보여야 함")
            if shot.get('hands_visible_needed'):
                print(f"  [!] 손 제스처가 보여야 함")

        # 자세 가이드
        if 'body_posture' in detailed and detailed['body_posture']:
            posture = detailed['body_posture']
            if posture.get('issues_count', 0) > 0:
                print(f"\n- 자세 교정사항 ({posture['issues_count']}개):")
                for corr in posture.get('corrections', []):
                    print(f"  - {corr['issue']}: {corr['action']}")

        # 표정 가이드
        if 'facial_expression' in detailed and detailed['facial_expression']:
            face = detailed['facial_expression']
            detail_level_kr = {'high': '높음', 'low': '낮음'}
            print(f"\n- 얼굴 표정:")
            print(f"  디테일 수준: {detail_level_kr.get(face.get('detail_level', ''), face.get('detail_level', '알수없음'))}")
            if 'adjustment' in face:
                print(f"  -> {face['adjustment']}")

    # 포즈 분석 요약
    pose_analysis = result.get('pose_analysis', {})
    if pose_analysis:
        print("\n[포즈 분석 요약]")
        print("-" * 70)

        # 샷 타입
        if 'shot_type' in pose_analysis:
            shot = pose_analysis['shot_type']
            curr_shot = shot.get('current', {})
            ref_shot = shot.get('reference', {})

            # 샷 타입 한글화
            shot_type_kr = {
                'extreme_closeup': '익스트림 클로즈업',
                'closeup': '클로즈업',
                'bust_shot': '바스트샷',
                'medium_shot': '미디엄샷',
                'knee_shot': '무릎샷',
                'full_shot': '전신샷',
                'long_shot': '롱샷'
            }

            curr_type = shot_type_kr.get(curr_shot.get('type', ''), curr_shot.get('type', '알수없음'))
            ref_type = shot_type_kr.get(ref_shot.get('type', ''), ref_shot.get('type', '알수없음'))

            print(f"\n- 샷 타입: {curr_type} -> {ref_type}")
            if not shot.get('match'):
                print(f"  [!] 샷 타입 불일치 - 조정 필요")

        # 얼굴 방향
        if 'face_direction' in pose_analysis and pose_analysis['face_direction']:
            face = pose_analysis['face_direction']
            if 'current' in face and face['current']:
                curr_dir = face['current'].get('horizontal_rotation', {}).get('direction', '알수없음')
                print(f"\n- 얼굴 방향: {curr_dir}")
                if not face.get('match'):
                    print(f"  [!] 얼굴 방향 조정 필요")

        # 손 제스처
        if 'hand_gestures' in pose_analysis and pose_analysis['hand_gestures']:
            hands = pose_analysis['hand_gestures']
            curr_hands = hands.get('current', {})
            if curr_hands:
                gestures = []
                if curr_hands.get('left'):
                    gesture = curr_hands['left'].get('gesture', '알수없음')
                    gestures.append(f"왼손: {gesture}")
                if curr_hands.get('right'):
                    gesture = curr_hands['right'].get('gesture', '알수없음')
                    gestures.append(f"오른손: {gesture}")
                if gestures:
                    print(f"\n- 손 제스처: {' | '.join(gestures)}")

    # 최종 권장사항
    print("\n" + "="*70)
    print("[다음 단계]")
    print("="*70)

    if priority_actions:
        print(f"\n1. 먼저 시작하세요: {priority_actions[0]['action']}")
        print(f"2. 총 조정 필요 항목: {len(priority_actions)}개")
        print(f"3. 예상 개선 점수: +{feedback.get('improvement_potential', 0):.0f}점")
    else:
        print("\n[OK] 레퍼런스와 매우 유사합니다!")
        print("  완벽을 위한 미세 조정만 필요")

    print("\n" + "="*70)


def main():
    """메인 실행 함수"""

    try:
        # 언어 선택
        print("\n" + "="*70)
        print("  TryAngle v1.5 - 133 Keypoint Enhanced Comparison  ")
        print("="*70)
        print("\n[Language / 언어]")
        print("  1. 한국어 (Korean)")
        print("  2. English")
        lang_choice = input("Select / 선택 (1-2, default=1): ").strip()

        language = 'ko'  # 기본값
        if lang_choice == '2':
            language = 'en'

        # 언어 설정
        set_language(language)
        config = get_config(language)

        print("\n" + "="*70)
        if language == 'ko':
            print("\nRTMPose Wholebody 기반 (133개 키포인트)")
            print("- 신체: 17개 키포인트")
            print("- 얼굴: 68개 랜드마크")
            print("- 손: 42개 키포인트 (각 21개)")
            print("- 발: 6개 키포인트")
        else:
            print("\nPowered by RTMPose Wholebody (133 keypoints)")
            print("- Body: 17 keypoints")
            print("- Face: 68 landmarks")
            print("- Hands: 42 keypoints (21 each)")
            print("- Feet: 6 keypoints")
        print("="*70)

        # 이미지 경로 입력
        if language == 'ko':
            print("\n[이미지 입력]")
            print("-" * 40)
            current_prompt = "현재 이미지 경로: "
            reference_prompt = "레퍼런스 이미지 경로: "
            not_found_msg = "파일을 찾을 수 없습니다: "
        else:
            print("\n[Image Input]")
            print("-" * 40)
            current_prompt = "Current image path: "
            reference_prompt = "Reference image path: "
            not_found_msg = "File not found: "

        current_path = input(current_prompt).strip().replace('"', '').replace("'", '')
        if not Path(current_path).exists():
            print(f"{not_found_msg}{current_path}")
            return

        reference_path = input(reference_prompt).strip().replace('"', '').replace("'", '')
        if not Path(reference_path).exists():
            print(f"{not_found_msg}{reference_path}")
            return

        # 기기 타입 선택
        if language == 'ko':
            print("\n[기기 선택] (선택사항, Enter로 건너뛰기)")
        else:
            print("\n[Device Selection] (Optional, press Enter to skip)")
        print("  1. iPhone")
        print("  2. Galaxy")
        if language == 'ko':
            print("  3. 기타/일반")
            device_prompt = "선택 (1-3): "
        else:
            print("  3. Generic/Other")
            device_prompt = "Select (1-3): "

        device_choice = input(device_prompt).strip()

        device_type = "generic"
        if device_choice == "1":
            device_type = "iPhone"
        elif device_choice == "2":
            device_type = "Galaxy"

        # 분석 실행
        if language == 'ko':
            print("\n[처리 중...]")
        else:
            print("\n[Processing...]")
        print("-" * 40)

        feedback_gen = ImprovedFeedbackV3()
        start_time = time.time()

        result = feedback_gen.compare_with_keypoints(
            current_path=current_path,
            reference_path=reference_path,
            device_type=device_type
        )

        total_time = time.time() - start_time

        # 결과 출력
        print_enhanced_feedback_v3(result, device_type, language)

        if language == 'ko':
            print(f"\n분석 시간: {total_time:.1f}초")
        else:
            print(f"\nAnalysis time: {total_time:.1f}s")

        # 결과 저장 옵션
        if language == 'ko':
            save_prompt = "\n분석 결과를 저장하시겠습니까? (y/n): "
            saved_msg = "결과가 저장되었습니다: "
        else:
            save_prompt = "\nSave analysis results? (y/n): "
            saved_msg = "Results saved to: "

        save_option = input(save_prompt).lower()
        if save_option == 'y':
            output_path = Path(current_path).stem + "_analysis_v3.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"{saved_msg}{output_path}")

        # 재실행 여부
        print("\n" + "="*70)
        if language == 'ko':
            again_prompt = "\n다른 이미지를 비교하시겠습니까? (y/n): "
            thanks_msg = "\nTryAngle v1.5를 사용해주셔서 감사합니다!"
        else:
            again_prompt = "\nCompare another pair? (y/n): "
            thanks_msg = "\nThank you for using TryAngle v1.5!"

        again = input(again_prompt).lower()
        if again == 'y':
            main()
        else:
            print(thanks_msg)

    except KeyboardInterrupt:
        print("\n\n종료합니다..." if 'language' in locals() and language == 'ko' else "\n\nExiting...")
    except Exception as e:
        if 'language' in locals() and language == 'ko':
            print(f"\n오류: {e}")
        else:
            print(f"\nError: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()