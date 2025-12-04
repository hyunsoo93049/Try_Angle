#!/usr/bin/env python3
"""
TryAngle v1.5 - Smart Feedback v5 DEBUG VERSION
디버그 정보 상세 출력 버전
하이앵글 전신샷 감지 개선
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

# Framing Analyzer 임포트 (새로운 프레이밍 분석)
from framing_analyzer import FramingAnalyzer

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


class SmartFeedbackV5Debug:
    """
    Gate System v5 Debug: 상세 디버그 정보 출력
    """

    def __init__(self, language='ko'):
        """초기화"""
        print(f"[DEBUG MODE] SmartFeedbackV5 Debug Version")
        print(f"[SmartFeedbackV5Debug] 초기화 중... (언어: {language})")

        # 133개 키포인트 분석기
        self.wholebody = RTMPoseWholebodyAnalyzer(mode='balanced')

        # Legacy 시스템 (v2 압축감 로직)
        self.legacy_comparator = ReferenceComparison()

        # 프레이밍 분석기 (새로운)
        self.framing_analyzer = FramingAnalyzer()

        # 언어 설정
        self.config = get_config(language)
        self.language = language

        # Gate 통과 기준
        self.gate_thresholds = {
            'aspect_ratio': 90,
            'framing': 70,
            'composition': 75,
            'compression': 80
        }

        # 디바이스별 줌 시스템
        self.device_zoom_systems = {
            "iPhone": [0.5, 1.0, 2.0, 3.0, 5.0],
            "Galaxy": [0.6, 1.0, 3.0, 10.0],
            "generic": [0.5, 1.0, 2.0, 3.0, 5.0]
        }

        print("[SmartFeedbackV5Debug] 초기화 완료")

    def analyze_with_gates(self, current_path: str, reference_path: str,
                          device_type: str = "generic",
                          test_mode: bool = True) -> Dict[str, Any]:
        """
        Gate System 기반 분석 (디버그 모드)
        """
        print("\n" + "="*70)
        print("[DEBUG] Gate System v5 Debug Mode 분석 시작")
        print("="*70)

        print(f"\n[입력 파일 정보]")
        print(f"  Current: {Path(current_path).name}")
        print(f"  Reference: {Path(reference_path).name}")

        # 이미지 로드
        curr_img = self._load_image(current_path)
        ref_img = self._load_image(reference_path)

        if curr_img is None or ref_img is None:
            return {'error': '이미지 로드 실패'}

        print(f"\n[이미지 크기]")
        print(f"  Current: {curr_img.shape[1]}x{curr_img.shape[0]} (WxH)")
        print(f"  Reference: {ref_img.shape[1]}x{ref_img.shape[0]} (WxH)")

        # 133개 키포인트 추출 (상세 디버그)
        print("\n[133개 키포인트 추출 - 상세]")
        print("-" * 60)

        curr_kpts = self._extract_keypoints_debug(curr_img, "Current")
        ref_kpts = self._extract_keypoints_debug(ref_img, "Reference")

        # Legacy 분석
        print("\n[Legacy 시스템 분석]")
        print("-" * 60)
        legacy_result = self.legacy_comparator.compare(
            current_path=current_path,
            reference_path=reference_path,
            mode='detailed'
        )

        # Gate System 적용 (Full Analysis Mode)
        return self._full_analysis_debug(
            curr_kpts, ref_kpts,
            curr_img.shape, ref_img.shape,
            legacy_result, device_type
        )

    def _extract_keypoints_debug(self, img: np.ndarray, label: str) -> Dict:
        """키포인트 추출 (상세 디버그)"""

        print(f"\n[{label} 이미지 키포인트 분석]")

        kpts = self.wholebody.extract_wholebody_keypoints(img)

        print(f"  인물 수: {kpts['num_persons']}명")

        if kpts['num_persons'] > 0:
            # 신체 키포인트
            body_kpts = kpts.get('body_keypoints', {})
            print(f"\n  [신체 키포인트] {len(body_kpts)}개 검출")

            # 주요 부위 체크
            key_parts = ['nose', 'left_shoulder', 'right_shoulder',
                        'left_hip', 'right_hip', 'left_knee', 'right_knee',
                        'left_ankle', 'right_ankle']

            for part in key_parts:
                if part in body_kpts:
                    pos = body_kpts[part]['position']
                    conf = body_kpts[part].get('confidence', 0)
                    print(f"    {part:15s}: 위치({pos[0]:4.0f}, {pos[1]:4.0f}) 신뢰도={conf:.2f}")
                else:
                    print(f"    {part:15s}: [미검출]")

            # 발 키포인트 (6개)
            foot_kpts = kpts.get('foot_keypoints', {})
            print(f"\n  [발 키포인트] {len(foot_kpts)}개 검출")

            foot_parts = ['left_big_toe', 'left_small_toe', 'left_heel',
                         'right_big_toe', 'right_small_toe', 'right_heel']

            for part in foot_parts:
                if part in foot_kpts:
                    pos = foot_kpts[part]['position']
                    conf = foot_kpts[part].get('confidence', 0)
                    print(f"    {part:15s}: 위치({pos[0]:4.0f}, {pos[1]:4.0f}) 신뢰도={conf:.2f}")
                else:
                    print(f"    {part:15s}: [미검출]")

            # 얼굴 랜드마크
            face_landmarks = kpts.get('face_landmarks', {})
            print(f"\n  [얼굴 랜드마크] {len(face_landmarks)}개 검출")

            # 손 키포인트
            left_hand = kpts.get('left_hand', {})
            right_hand = kpts.get('right_hand', {})
            print(f"\n  [손 키포인트]")
            print(f"    왼손: {len(left_hand)}개")
            print(f"    오른손: {len(right_hand)}개")

            # 하이앵글 감지 (발목과 머리의 Y 좌표 비교)
            if 'nose' in body_kpts and ('left_ankle' in body_kpts or 'right_ankle' in body_kpts):
                nose_y = body_kpts['nose']['position'][1]

                ankle_ys = []
                if 'left_ankle' in body_kpts:
                    ankle_ys.append(body_kpts['left_ankle']['position'][1])
                if 'right_ankle' in body_kpts:
                    ankle_ys.append(body_kpts['right_ankle']['position'][1])

                if ankle_ys:
                    avg_ankle_y = np.mean(ankle_ys)
                    height_ratio = (avg_ankle_y - nose_y) / img.shape[0]

                    print(f"\n  [하이앵글 분석]")
                    print(f"    머리 Y: {nose_y:.0f}")
                    print(f"    발목 Y: {avg_ankle_y:.0f}")
                    print(f"    신장 비율: {height_ratio:.2f} (이미지 높이 대비)")

                    if height_ratio > 0.6:
                        print(f"    -> 전신이 포함됨 (비율 > 0.6)")
                    elif height_ratio > 0.4:
                        print(f"    -> 대부분의 신체가 포함됨")
                    else:
                        print(f"    -> 상반신 위주")

        return kpts

    def _full_analysis_debug(self, curr_kpts: Dict, ref_kpts: Dict,
                             curr_shape: Tuple, ref_shape: Tuple,
                             legacy_result: Any, device_type: str) -> Dict[str, Any]:
        """
        디버그 모드: 모든 Gate 상세 분석
        """
        print("\n" + "="*70)
        print("[DEBUG] Full Analysis Mode - 모든 Gate 점검")
        print("="*70)

        all_gates = {}

        # ============ GATE 0: 종횡비 체크 ============
        print("\n[GATE 0] 종횡비 체크...")
        aspect_score, aspect_feedback = self._check_aspect_ratio_debug(curr_shape, ref_shape)
        all_gates['aspect_ratio'] = {
            'score': aspect_score,
            'passed': aspect_score >= self.gate_thresholds['aspect_ratio'],
            'feedback': aspect_feedback
        }

        # ============ GATE 1: 프레이밍 (샷 타입) ============
        print("\n[GATE 1] 프레이밍 체크...")
        framing_score, framing_result = self._check_framing_debug(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )
        all_gates['framing'] = {
            'score': framing_score,
            'passed': framing_score >= self.gate_thresholds['framing'],
            'feedback': framing_result.get('feedback', {}).get('summary', ''),
            'details': framing_result  # 상세 분석 결과 포함
        }

        # ============ GATE 2: 구도 ============
        print("\n[GATE 2] 구도 체크...")
        composition_score, composition_feedback = self._check_composition_debug(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )
        all_gates['composition'] = {
            'score': composition_score,
            'passed': composition_score >= self.gate_thresholds['composition'],
            'feedback': composition_feedback
        }

        # ============ GATE 3: 압축감 ============
        print("\n[GATE 3] 압축감 체크...")
        compression_score, compression_feedback = self._check_compression_debug(
            legacy_result, device_type
        )
        all_gates['compression'] = {
            'score': compression_score,
            'passed': compression_score >= self.gate_thresholds['compression'],
            'feedback': compression_feedback
        }

        # ============ GATE 4: 포즈 세부 ============
        print("\n[GATE 4] 포즈 세부 체크...")
        pose_feedback = self._check_pose_details_debug(curr_kpts, ref_kpts)
        all_gates['pose'] = {
            'feedback': pose_feedback
        }

        # 전체 점수 계산
        scores = [g['score'] for g in all_gates.values() if 'score' in g]
        overall_score = sum(scores) / len(scores) if scores else 0

        print(f"\n[최종 점수] {overall_score:.1f}/100")

        # 친절한 요약 코멘트 생성
        friendly_summary = self._generate_friendly_summary(all_gates, overall_score)

        return {
            'mode': 'DEBUG_ANALYSIS',
            'overall_score': overall_score,
            'all_gates': all_gates,
            'summary': self._generate_summary(all_gates),
            'friendly_summary': friendly_summary
        }

    def _generate_friendly_summary(self, all_gates: Dict, overall_score: float) -> str:
        """친절한 요약 코멘트 생성"""

        passed = []
        failed = []

        # 구도 실패 시 구체적 움직임 포함
        composition_feedback = None

        for gate_name, gate_data in all_gates.items():
            if 'passed' in gate_data:
                if gate_data['passed']:
                    if gate_name == 'aspect_ratio':
                        passed.append('종횡비')
                    elif gate_name == 'framing':
                        passed.append('샷 타입')
                    elif gate_name == 'composition':
                        passed.append('구도')
                    elif gate_name == 'compression':
                        passed.append('압축감')
                else:
                    if gate_name == 'aspect_ratio':
                        failed.append('종횡비')
                    elif gate_name == 'framing':
                        failed.append('샷 타입')
                    elif gate_name == 'composition':
                        failed.append('구도')
                        # 구도 실패 시 액션 가능한 피드백 체크
                        if 'details' in gate_data and 'actionable_feedback' in gate_data['details']:
                            actionable = gate_data['details']['actionable_feedback']
                            if actionable.get('has_actionable'):
                                # 첫 번째 움직임만 추가
                                actions = actionable.get('priority_actions', [])
                                if actions:
                                    composition_feedback = actions[0].get('camera_action', '')
                    elif gate_name == 'compression':
                        failed.append('압축감')

        # 요약 메시지 (더 현실적인 임계값)
        if overall_score >= 95:
            return "거의 완벽합니다! 레퍼런스와 매우 유사해요."
        elif overall_score >= 85:
            if len(failed) == 1:
                if failed[0] == '구도' and composition_feedback:
                    return f"레퍼런스와 비슷합니다. {composition_feedback}하면 더 좋아질 거예요."
                else:
                    return f"레퍼런스와 비슷합니다. {failed[0]}만 조정하면 더 좋아질 거예요."
            else:
                return "레퍼런스와 비슷하지만 미세 조정이 필요합니다."
        elif overall_score >= 75:
            if len(passed) >= 2:
                if '구도' in failed and composition_feedback:
                    return f"{', '.join(passed)}은(는) 잘 맞지만, {composition_feedback}가 필요해요."
                else:
                    return f"{', '.join(passed)}은(는) 잘 맞지만, {', '.join(failed)}은(는) 조정이 필요해요."
            else:
                return "전반적으로 괜찮지만 몇 가지 개선이 필요합니다."
        elif overall_score >= 65:
            if '구도' in failed and composition_feedback:
                return f"레퍼런스와 차이가 있으니 {composition_feedback}가 필요합니다."
            else:
                return "레퍼런스와 차이가 있으니 조정이 필요합니다."
        else:
            if '구도' in failed and composition_feedback:
                return f"상당한 차이가 있어요. 먼저 {composition_feedback}해 보세요."
            else:
                return "상당한 차이가 있어 단계적 조정이 필요해요."

    def _check_aspect_ratio_debug(self, curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """종횡비 체크 (디버그)"""

        curr_ratio = curr_shape[1] / curr_shape[0]
        ref_ratio = ref_shape[1] / ref_shape[0]

        # 종횡비 이름 판별
        def get_ratio_name(ratio):
            if abs(ratio - 1.0) < 0.1:
                return "1:1 (정사각형)"
            elif abs(ratio - 1.33) < 0.1:
                return "4:3 (표준)"
            elif abs(ratio - 1.5) < 0.1:
                return "3:2 (DSLR)"
            elif abs(ratio - 1.78) < 0.1:
                return "16:9 (와이드)"
            elif abs(ratio - 0.75) < 0.1:
                return "3:4 (세로)"
            elif abs(ratio - 0.56) < 0.1:
                return "9:16 (세로 와이드)"
            else:
                return f"{ratio:.2f}:1"

        curr_name = get_ratio_name(curr_ratio)
        ref_name = get_ratio_name(ref_ratio)

        print(f"  Current 종횡비: {curr_ratio:.3f} = {curr_name}")
        print(f"  Reference 종횡비: {ref_ratio:.3f} = {ref_name}")

        diff = abs(curr_ratio - ref_ratio)
        print(f"  차이: {diff:.3f}")

        if diff < 0.1:
            print(f"  -> 종횡비 일치 (차이 < 0.1)")
            return 100, None

        score = max(30, 100 - (diff * 100))
        print(f"  -> 종횡비 불일치 (점수: {score:.0f})")
        print(f"  -> 조정 필요: 종횡비를 {curr_name}에서 {ref_name}으로 변경하세요")

        return score, {
            'issue': 'ASPECT_RATIO_MISMATCH',
            'diff': diff,
            'current_name': curr_name,
            'target_name': ref_name,
            'action': f"종횡비를 {curr_name}에서 {ref_name}으로 변경하세요"
        }

    def _check_framing_debug(self, curr_kpts: Dict, ref_kpts: Dict,
                             curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """프레이밍 체크 - 종합 분석 (디버그)"""

        print("\n  [프레이밍 종합 분석]")
        print("  " + "-"*50)

        # FramingAnalyzer로 종합 분석
        framing_result = self.framing_analyzer.analyze_framing_comprehensive(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        # 0. 인물 방향 정보
        if 'person_orientation' in framing_result:
            orient = framing_result['person_orientation']
            print(f"\n  [0] 인물 방향")
            print(f"     Current: {orient['current'].get('direction', 'unknown')}")
            print(f"     Reference: {orient['reference'].get('direction', 'unknown')}")

        # 1. 샷 타입 분석
        shot_data = framing_result['shot_type']
        print(f"\n  [1] 샷 타입 분석")
        curr_name_kr = shot_data['current'].get('name_kr', shot_data['current'].get('type', 'unknown'))
        ref_name_kr = shot_data['reference'].get('name_kr', shot_data['reference'].get('type', 'unknown'))

        print(f"     Current: {curr_name_kr}")
        if 'lowest' in shot_data['current']:
            print(f"       최하단: {shot_data['current']['lowest']}")
        elif 'direction' in shot_data['current']:
            print(f"       방향: {shot_data['current']['direction']}")
        print(f"     Reference: {ref_name_kr}")
        if 'lowest' in shot_data['reference']:
            print(f"       최하단: {shot_data['reference']['lowest']}")
        elif 'direction' in shot_data['reference']:
            print(f"       방향: {shot_data['reference']['direction']}")

        if shot_data['same_category']:
            print(f"     -> 같은 카테고리 (점수: {shot_data['score']:.0f})")
        else:
            print(f"     -> 다른 카테고리 (점수: {shot_data['score']:.0f})")

        # 2. 인물 비중 분석
        subject_data = framing_result['subject_ratio']
        print(f"\n  [2] 인물 비중 분석")
        print(f"     Current: 화면의 {subject_data['current_ratio']*100:.1f}% 차지")
        print(f"     Reference: 화면의 {subject_data['reference_ratio']*100:.1f}% 차지")

        if subject_data['direction'] == 'smaller':
            print(f"     -> 인물이 더 작게 들어감 (점수: {subject_data['score']:.0f})")
        elif subject_data['direction'] == 'larger':
            print(f"     -> 인물이 더 크게 들어감 (점수: {subject_data['score']:.0f})")
        else:
            print(f"     -> 비슷한 크기 (점수: {subject_data['score']:.0f})")

        # 3. 하단 여백(테이블) 분석
        bottom_data = framing_result['bottom_space']
        print(f"\n  [3] 하단 여백 분석")
        print(f"     Current: 하단 {bottom_data['current_ratio']*100:.1f}% (인물 아래 공간)")
        print(f"     Reference: 하단 {bottom_data['reference_ratio']*100:.1f}%")

        if bottom_data['table_heavy']:
            print(f"     -> 테이블/하단이 많이 보임 (테이블 위주 구도)")

        if bottom_data['direction'] == 'too_much_bottom':
            print(f"     -> 하단 여백 과다 (점수: {bottom_data['score']:.0f})")
        elif bottom_data['direction'] == 'too_little_bottom':
            print(f"     -> 하단 여백 부족 (점수: {bottom_data['score']:.0f})")
        else:
            print(f"     -> 적절한 여백 (점수: {bottom_data['score']:.0f})")

        # 4. 4방향 여백 분석 (새로 추가)
        if 'all_margins' in framing_result:
            margins = framing_result['all_margins']
            print(f"\n  [4] 4방향 여백 분석")

            curr_m = margins['current']
            ref_m = margins['reference']

            print(f"     Current 여백:")
            print(f"       상:{curr_m['top']*100:.0f}% 하:{curr_m['bottom']*100:.0f}% " +
                  f"좌:{curr_m['left']*100:.0f}% 우:{curr_m['right']*100:.0f}%")
            print(f"     Reference 여백:")
            print(f"       상:{ref_m['top']*100:.0f}% 하:{ref_m['bottom']*100:.0f}% " +
                  f"좌:{ref_m['left']*100:.0f}% 우:{ref_m['right']*100:.0f}%")

            if margins['center_alignment']['aligned']:
                print(f"     -> 중앙 정렬 OK")
            else:
                print(f"     -> 중앙 정렬 필요")

        # 4. 종합 점수 및 피드백
        overall_score = framing_result['overall_score']
        feedback_data = framing_result['feedback']

        print(f"\n  [종합 프레이밍 점수] {overall_score:.0f}/100")
        print(f"     (샷타입 30% + 인물비중 40% + 하단여백 30%)")

        if feedback_data['severity'] == 'perfect':
            print(f"     -> 프레이밍 완벽!")
        elif feedback_data['severity'] == 'minor':
            print(f"     -> 미세 조정 필요")
        else:
            print(f"     -> 프레이밍 조정 필요")

        # 친절한 피드백
        if feedback_data['friendly_message']:
            print(f"\n  [피드백]")
            for line in feedback_data['friendly_message'].split(". "):
                if line.strip():
                    print(f"     - {line.strip()}")

        # 구체적인 액션 (기존)
        if feedback_data['actions']:
            print(f"\n  [권장 조정]")
            for i, action in enumerate(feedback_data['actions'][:3], 1):
                print(f"     {i}. {action}")

        # 액션 가능한 피드백 (새로 추가)
        if 'actionable_feedback' in framing_result:
            actionable = framing_result['actionable_feedback']
            if actionable['has_actionable']:
                print(f"\n  [구체적 조정 방법]")
                print("  " + "-"*50)
                for line in actionable['message'].split('\n'):
                    if line.strip():
                        print(f"  {line}")

        # 종합 움직임 가이드 (새로 추가)
        if 'comprehensive_guide' in framing_result:
            guide = framing_result['comprehensive_guide']
            if guide.get('movements'):
                print(f"\n  [종합 조정 가이드]")
                print("  " + "-"*50)
                for move in guide['movements']:
                    print(f"  {move['step']}단계: {move['instruction']}")
                    if 'alternative' in move:
                        print(f"         또는 {move['alternative']}")
                    if 'effect' in move:
                        print(f"         효과: {move['effect']}")

        return overall_score, framing_result

    def _determine_shot_type_highangle(self, kpts: Dict, img_shape: Tuple) -> Dict[str, Any]:
        """하이앵글 촬영을 고려한 샷 타입 판별"""

        if kpts['num_persons'] == 0:
            return {'type': 'unknown', 'description': '인물 없음', 'reason': '키포인트 검출 실패'}

        body = kpts.get('body_keypoints', {})
        foot = kpts.get('foot_keypoints', {})

        # 1. 발 키포인트 체크 (최우선)
        if len(foot) >= 3:  # 6개 중 3개 이상 (하이앵글에서는 기준 완화)
            return {
                'type': 'full_shot',
                'description': '전신샷',
                'reason': f'발 키포인트 {len(foot)}개 검출',
                'confidence': 0.9
            }

        # 2. 발목 체크 (하이앵글에서 중요)
        if 'left_ankle' in body or 'right_ankle' in body:
            # 발목이 있고 머리도 있으면 전신일 가능성 높음
            if 'nose' in body or 'neck' in body:
                # 신장 비율 체크
                head_y = body.get('nose', body.get('neck', {})).get('position', [0, 0])[1]
                ankle_ys = []
                if 'left_ankle' in body:
                    ankle_ys.append(body['left_ankle']['position'][1])
                if 'right_ankle' in body:
                    ankle_ys.append(body['right_ankle']['position'][1])

                if ankle_ys:
                    avg_ankle_y = np.mean(ankle_ys)
                    height_ratio = (avg_ankle_y - head_y) / img_shape[0]

                    if height_ratio > 0.5:  # 이미지 높이의 50% 이상
                        return {
                            'type': 'full_shot',
                            'description': '전신샷 (하이앵글)',
                            'reason': f'발목 검출, 신장비율 {height_ratio:.2f}',
                            'confidence': 0.85
                        }

        # 3. 무릎 체크
        if 'left_knee' in body or 'right_knee' in body:
            return {
                'type': 'knee_shot',
                'description': '무릎샷',
                'reason': '무릎 검출',
                'confidence': 0.8
            }

        # 4. 엉덩이 체크
        if 'left_hip' in body and 'right_hip' in body:
            return {
                'type': 'medium_shot',
                'description': '미디엄샷',
                'reason': '엉덩이 검출',
                'confidence': 0.75
            }

        # 5. 어깨만 보임
        if 'left_shoulder' in body and 'right_shoulder' in body:
            if len(kpts.get('face_landmarks', {})) > 50:
                return {
                    'type': 'bust_shot',
                    'description': '바스트샷',
                    'reason': '어깨+얼굴 검출',
                    'confidence': 0.7
                }
            else:
                return {
                    'type': 'closeup',
                    'description': '클로즈업',
                    'reason': '어깨만 검출',
                    'confidence': 0.65
                }

        # 6. 얼굴만
        if len(kpts.get('face_landmarks', {})) > 60:
            return {
                'type': 'extreme_closeup',
                'description': '익스트림 클로즈업',
                'reason': '얼굴 랜드마크만 검출',
                'confidence': 0.7
            }

        return {
            'type': 'unknown',
            'description': '판별 불가',
            'reason': '키포인트 부족',
            'confidence': 0.1
        }

    def _check_composition_debug(self, curr_kpts: Dict, ref_kpts: Dict,
                                 curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """구도 체크 (디버그)"""

        print("\n  [구도 분석]")

        curr_center = self._calculate_face_center(curr_kpts, curr_shape)
        ref_center = self._calculate_face_center(ref_kpts, ref_shape)

        if curr_center:
            print(f"  Current 얼굴 중심: ({curr_center[0]:.2f}, {curr_center[1]:.2f})")
            curr_grid = self._to_grid_position(curr_center)
            print(f"    3분할 위치: {curr_grid}")
        else:
            print(f"  Current 얼굴 중심: 검출 실패")
            return 75, None

        if ref_center:
            print(f"  Reference 얼굴 중심: ({ref_center[0]:.2f}, {ref_center[1]:.2f})")
            ref_grid = self._to_grid_position(ref_center)
            print(f"    3분할 위치: {ref_grid}")
        else:
            print(f"  Reference 얼굴 중심: 검출 실패")
            return 75, None

        if curr_grid == ref_grid:
            print(f"  -> 구도 일치 (90점)")
            return 90, None

        distance = math.sqrt((curr_center[0] - ref_center[0])**2 +
                           (curr_center[1] - ref_center[1])**2)
        score = max(40, 80 - (distance * 100))

        # ⭐ 액션 가능한 피드백 생성
        position_movements = self.framing_analyzer._analyze_position_movements(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        actionable_feedback = self.framing_analyzer.generate_actionable_feedback(
            position_movements, [], score
        )

        # 구도 불일치 + 구체적 조정 방법 출력
        x_diff = ref_center[0] - curr_center[0]
        y_diff = ref_center[1] - curr_center[1]

        print(f"  -> 구도 불일치 (점수: {score:.0f})")

        # 구체적 움직임 지시 즉시 출력
        if abs(x_diff) > 0.05:
            percent_x = abs(x_diff) * 100
            if x_diff > 0:
                print(f"     -> 카메라를 왼쪽으로 {percent_x:.0f}% 이동")
                print(f"        또는 인물이 오른쪽으로 {self._to_steps_simple(percent_x)} 이동")
            else:
                print(f"     -> 카메라를 오른쪽으로 {percent_x:.0f}% 이동")
                print(f"        또는 인물이 왼쪽으로 {self._to_steps_simple(percent_x)} 이동")

        if abs(y_diff) > 0.05:
            percent_y = abs(y_diff) * 100
            angle = min(int(percent_y * 0.5), 15)
            if y_diff > 0:
                print(f"     -> 카메라를 {angle}도 아래로 틸트")
            else:
                print(f"     -> 카메라를 {angle}도 위로 틸트")

        return score, {
            'issue': 'POSITION_MISMATCH',
            'current_grid': curr_grid,
            'target_grid': ref_grid,
            'actionable_feedback': actionable_feedback
        }

    def _to_steps_simple(self, percent: float) -> str:
        """퍼센트를 걸음수로 변환 (간단 버전)"""
        if percent < 10:
            return "반 걸음"
        elif percent < 20:
            return "한 걸음"
        elif percent < 30:
            return "두 걸음"
        elif percent < 40:
            return "세 걸음"
        else:
            return "네 걸음 이상"

    def _check_compression_debug(self, legacy_result: Any, device_type: str) -> Tuple[float, Optional[Dict]]:
        """압축감 체크 (디버그)"""

        print("\n  [압축감 분석]")

        if not hasattr(legacy_result, 'detailed_feedback'):
            print("  Legacy 결과 없음")
            return 80, None

        if 'compression' not in legacy_result.detailed_feedback:
            print("  압축감 데이터 없음")
            return 80, None

        comp_data = legacy_result.detailed_feedback['compression']

        import re
        curr_match = re.search(r'\(([0-9.]+)\)', comp_data.get('current', ''))
        ref_match = re.search(r'\(([0-9.]+)\)', comp_data.get('reference', ''))

        if not (curr_match and ref_match):
            print("  압축값 추출 실패")
            return 80, None

        curr_comp = float(curr_match.group(1))
        ref_comp = float(ref_match.group(1))

        # 압축감 구간 설명 (3단계 단순화)
        def describe_compression(value):
            if value < 0.35:
                return "광각 쪽"
            elif value < 0.65:
                return "중간 정도"
            else:
                return "압축된 느낌"

        print(f"  Current 압축값: {curr_comp:.2f} ({describe_compression(curr_comp)})")
        print(f"  Reference 압축값: {ref_comp:.2f} ({describe_compression(ref_comp)})")
        print(f"  차이: {abs(ref_comp - curr_comp):.2f}")

        diff = abs(ref_comp - curr_comp)

        if diff < 0.05:
            print(f"  -> 압축감 일치 (95점)")
            return 95, None

        # 더 관대한 점수 계산
        if diff < 0.2:
            score = 95 - (diff - 0.05) * 100
        elif diff < 0.4:
            score = 80 - (diff - 0.2) * 75
        else:
            score = max(50, 65 - (diff - 0.4) * 50)

        print(f"  -> 압축감 차이 있음 (점수: {score:.0f})")

        # 상대적 조정 방향 (친절하고 완만한 표현)
        actions = []
        if curr_comp < ref_comp:
            # 강도를 더 세밀하게 구분
            if diff < 0.1:
                intensity = "아주 조금"
                distance = "한 걸음 정도"
            elif diff < 0.25:
                intensity = "조금"
                distance = "한두 걸음"
            elif diff < 0.4:
                intensity = "어느 정도"
                distance = "몇 걸음"
            else:
                intensity = "꽤"
                distance = "여러 걸음"

            print(f"     조정: 레퍼런스보다 압축감이 {intensity} 약함 (wide 쪽)")
            print(f"     방법: 피사체에 {distance} 더 가까이 가거나 줌을 한 단계 확대")
            actions.append(f"피사체에 {distance} 더 가까이 가보세요")
            actions.append(f"또는 줌을 한 단계 확대해보세요")
        else:
            # 강도를 더 세밀하게 구분
            if diff < 0.1:
                intensity = "아주 조금"
                distance = "한 걸음 정도"
            elif diff < 0.25:
                intensity = "조금"
                distance = "한두 걸음"
            elif diff < 0.4:
                intensity = "어느 정도"
                distance = "몇 걸음"
            else:
                intensity = "꽤"
                distance = "여러 걸음"

            print(f"     조정: 레퍼런스보다 압축감이 {intensity} 강함 (압축된 쪽)")
            print(f"     방법: 피사체에서 {distance} 더 멀어지거나 줌을 한 단계 축소")
            actions.append(f"피사체에서 {distance} 더 멀어져보세요")
            actions.append(f"또는 줌을 한 단계 축소해보세요")

        return score, {
            'issue': 'COMPRESSION_MISMATCH',
            'current_compression': curr_comp,
            'target_compression': ref_comp,
            'current_desc': describe_compression(curr_comp),
            'target_desc': describe_compression(ref_comp),
            'actions': actions
        }

    def _check_pose_details_debug(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[List[Dict]]:
        """포즈 세부 체크 (디버그)"""

        print("\n  [포즈 세부 분석]")

        minor_adjustments = []

        # 어깨 정렬 체크
        curr_body = curr_kpts.get('body_keypoints', {})

        if 'left_shoulder' in curr_body and 'right_shoulder' in curr_body:
            curr_left = curr_body['left_shoulder']['position']
            curr_right = curr_body['right_shoulder']['position']

            # 어깨 기울기 계산 (올바른 방법)
            dx = curr_right[0] - curr_left[0]
            dy = curr_right[1] - curr_left[1]

            # atan2는 -π to π (-180 to 180도) 범위를 반환
            angle_rad = math.atan2(dy, dx)
            angle_deg = math.degrees(angle_rad)

            print(f"  어깨 각도: {angle_deg:.1f}도")
            print(f"    왼쪽 어깨: ({curr_left[0]:.0f}, {curr_left[1]:.0f})")
            print(f"    오른쪽 어깨: ({curr_right[0]:.0f}, {curr_right[1]:.0f})")

            # 수평(0도 또는 180도)에서 벗어난 정도 계산
            # 180도에 가까우면 180-abs(angle), 0도에 가까우면 abs(angle)
            if abs(angle_deg) > 90:
                # 180도 근처 (90~180 또는 -180~-90)
                deviation = abs(abs(angle_deg) - 180)
            else:
                # 0도 근처 (-90~90)
                deviation = abs(angle_deg)

            print(f"    수평 기준 편차: {deviation:.1f}도")

            if deviation < 5:
                print(f"    -> 어깨 완벽한 수평")
            elif deviation < 10:
                print(f"    -> 어깨 거의 수평 (자연스러움)")
            elif deviation < 20:
                minor_adjustments.append({
                    'category': 'posture',
                    'importance': 'optional',
                    'suggestion': f"어깨가 약간 기울어져 있습니다 ({deviation:.1f}도)"
                })
                print(f"    -> 어깨 약간 기울어짐")
            else:
                minor_adjustments.append({
                    'category': 'posture',
                    'importance': 'optional',
                    'suggestion': f"어깨가 기울어져 있습니다 ({deviation:.1f}도)"
                })
                print(f"    -> 어깨 기울어짐 감지")

        # 손 제스처 체크
        curr_right_hand = len(curr_kpts.get('right_hand', {}))
        ref_right_hand = len(ref_kpts.get('right_hand', {}))
        curr_left_hand = len(curr_kpts.get('left_hand', {}))
        ref_left_hand = len(ref_kpts.get('left_hand', {}))

        print(f"  손 키포인트:")
        print(f"    Current: 왼손={curr_left_hand}, 오른손={curr_right_hand}")
        print(f"    Reference: 왼손={ref_left_hand}, 오른손={ref_right_hand}")

        # 손 검출 이슈 친절하게 설명
        if ref_right_hand == 0 and ref_left_hand == 0 and (curr_right_hand > 10 or curr_left_hand > 10):
            print(f"    -> 레퍼런스에서 손이 검출되지 않음 (가려짐/프레임 밖 가능성)")
            minor_adjustments.append({
                'category': 'hand',
                'importance': 'info',
                'suggestion': '레퍼런스 이미지에서 손이 검출되지 않았습니다 (가려짐 또는 검출 실패)'
            })
        elif curr_right_hand == 0 and curr_left_hand == 0 and (ref_right_hand > 10 or ref_left_hand > 10):
            print(f"    -> 현재 이미지에서 손이 검출되지 않음")
            minor_adjustments.append({
                'category': 'hand',
                'importance': 'optional',
                'suggestion': '손이 더 잘 보이도록 조정해보세요 (조명 또는 각도 문제일 수 있음)'
            })
        elif abs((curr_right_hand + curr_left_hand) - (ref_right_hand + ref_left_hand)) > 15:
            print(f"    -> 손 제스처 차이 있을 수 있음")
            minor_adjustments.append({
                'category': 'hand',
                'importance': 'optional',
                'suggestion': f'손 제스처 차이가 있을 수 있습니다'
            })
        else:
            print(f"    -> 손 검출 OK")

        return minor_adjustments if minor_adjustments else None

    def _generate_summary(self, all_gates: Dict) -> str:
        """전체 분석 요약 생성"""

        summary = []

        gates_info = [
            ('aspect_ratio', '종횡비'),
            ('framing', '프레이밍'),
            ('composition', '구도'),
            ('compression', '압축감')
        ]

        for gate_key, gate_name in gates_info:
            if gate_key in all_gates:
                gate = all_gates[gate_key]
                if 'score' in gate:
                    status = "[OK]" if gate['passed'] else "[!]"
                    summary.append(f"{status} {gate_name}: {gate['score']:.0f}점")

        return "\n".join(summary)

    # Helper 함수들 (v5에서 가져옴)
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

    def _calculate_face_center(self, kpts: Dict, img_shape: Tuple) -> Optional[Tuple[float, float]]:
        """얼굴 중심 계산"""

        if kpts['num_persons'] == 0:
            return None

        face = kpts.get('face_landmarks', {})

        if len(face) > 30:
            positions = [kpt['position'] for kpt in face.values()]
            avg_x = np.mean([p[0] for p in positions]) / img_shape[1]
            avg_y = np.mean([p[1] for p in positions]) / img_shape[0]
            return (avg_x, avg_y)

        if 'nose' in kpts.get('body_keypoints', {}):
            nose = kpts['body_keypoints']['nose']['position']
            return (nose[0] / img_shape[1], nose[1] / img_shape[0])

        return None

    def _to_grid_position(self, pos: Tuple[float, float]) -> Tuple[int, int]:
        """3분할 구도 위치 변환"""
        grid_x = min(int(pos[0] * 3) + 1, 3)
        grid_y = min(int(pos[1] * 3) + 1, 3)
        return (grid_x, grid_y)


def main():
    """메인 실행 함수"""

    try:
        print("\n" + "="*70)
        print("  TryAngle v5 DEBUG VERSION  ")
        print("  키포인트 검출 상세 분석  ")
        print("="*70)

        # 시스템 초기화
        feedback_system = SmartFeedbackV5Debug(language='ko')

        # 이미지 입력
        print("\n[이미지 입력]")
        print("-" * 40)

        current_path = input("Current 이미지 경로: ").strip().replace('"', '').replace("'", '')
        if not Path(current_path).exists():
            print(f"파일을 찾을 수 없습니다: {current_path}")
            return

        reference_path = input("Reference 이미지 경로: ").strip().replace('"', '').replace("'", '')
        if not Path(reference_path).exists():
            print(f"파일을 찾을 수 없습니다: {reference_path}")
            return

        # 분석 실행
        print("\n[처리 중...]")

        start_time = time.time()

        result = feedback_system.analyze_with_gates(
            current_path=current_path,
            reference_path=reference_path,
            device_type='generic',
            test_mode=True
        )

        total_time = time.time() - start_time

        # 결과 출력
        print("\n" + "="*70)
        print("[분석 완료]")
        print("="*70)

        print(f"\n[전체 점수] {result.get('overall_score', 0):.0f}/100")

        print(f"\n[요약]")
        print(result.get('summary', ''))

        # 친절한 요약 코멘트
        if 'friendly_summary' in result:
            print(f"\n[친절한 피드백]")
            print(result.get('friendly_summary', ''))

        print(f"\n분석 시간: {total_time:.1f}초")

        # 재실행
        print("\n" + "="*70)
        again = input("\n다른 이미지를 비교하시겠습니까? (y/n): ").lower()
        if again == 'y':
            main()
        else:
            print("\nDebug 모드를 종료합니다.")

    except KeyboardInterrupt:
        print("\n\n종료합니다...")
    except Exception as e:
        print(f"\n오류: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()