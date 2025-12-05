#!/usr/bin/env python3
"""
TryAngle v7.0 - iOS Realtime Smart Feedback
기반: v6 + 실시간 최적화
개선 사항:
1. 이중 모드 (레퍼런스/실시간)
2. 캐싱 시스템
3. iOS 최적화
4. v6의 모든 기능 포함
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
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "models"))

# Analyzers 임포트
from analyzers.pose_analyzer import RTMPoseWholebodyAnalyzer
from analyzers.framing_analyzer import FramingAnalyzer
from analyzers.margin_analyzer import ImprovedMarginAnalyzer, convert_to_legacy_format

# Core 임포트
from feedback_config import FeedbackConfig, get_config, set_language

# Legacy 시스템 임포트 (레퍼런스 분석용)
from models.legacy.reference_comparison import (
    ReferenceComparison,
    ComparisonResult,
    ImageAnalysis
)

# 이미지 처리
try:
    from PIL import Image
except ImportError:
    import cv2


class SmartFeedbackV7:
    """
    iOS Realtime Smart Feedback System
    - v6 기반 + 실시간 최적화
    - 이중 모드: 레퍼런스 분석 / 실시간 처리
    - 캐싱 시스템 통합
    """

    def __init__(self, mode='ios', language='ko', debug_mode=True):
        """
        초기화
        Args:
            mode: 'ios' (실시간), 'reference' (정밀 분석), 'full' (둘 다)
            language: 언어 설정
            debug_mode: 디버그 출력
        """
        self.mode = mode
        self.debug_mode = debug_mode

        if debug_mode:
            print(f"[SmartFeedbackV7] 초기화 중... (모드: {mode}, 언어: {language})")
            print(f"[개선사항] iOS 실시간 최적화, 캐싱, 이중 모드")

        # 133개 키포인트 분석기
        self.wholebody = RTMPoseWholebodyAnalyzer(mode='balanced')

        # 모드별 초기화
        if mode in ['reference', 'full']:
            # Legacy 시스템 (레퍼런스 분석용)
            self.legacy_comparator = ReferenceComparison()
        else:
            # 실시간 모드에서는 Legacy 사용 안 함
            self.legacy_comparator = None

        # 프레이밍 분석기 (항상 사용)
        self.framing_analyzer = FramingAnalyzer()

        # 개선된 여백 분석기 (항상 사용)
        self.margin_analyzer = ImprovedMarginAnalyzer()

        # 캐시 관리자 (나중에 추가)
        self.cache_manager = None

        # 언어 설정
        self.config = get_config(language)
        self.language = language

        # Gate 통과 기준 (v5와 동일)
        self.gate_thresholds = {
            'aspect_ratio': 90,
            'framing': 70,
            'composition': 75,
            'compression': 80
        }

        # 디바이스별 줌 시스템 (v5와 동일)
        self.device_zoom_systems = {
            "iPhone": [0.5, 1.0, 2.0, 3.0, 5.0],
            "Galaxy": [0.6, 1.0, 3.0, 10.0],
            "generic": [0.5, 1.0, 2.0, 3.0, 5.0]
        }

        if debug_mode:
            print("[SmartFeedbackV7] 초기화 완료")

    def analyze_reference(self, reference_path: str) -> Dict[str, Any]:
        """
        레퍼런스 이미지 정밀 분석 (1회만 실행)
        Legacy 시스템 사용하여 정확한 분석
        """
        if self.debug_mode:
            print("\n" + "="*70)
            print("[레퍼런스 분석] 정밀 분석 시작...")
            print("="*70)

        if self.mode == 'ios' and self.legacy_comparator is None:
            # iOS 모드에서는 간소화된 분석
            return self._analyze_reference_fast(reference_path)
        else:
            # Full 모드에서는 Legacy 사용
            return self._analyze_reference_full(reference_path)

    def process_frame(self, frame: np.ndarray, reference_cache: Optional[Dict] = None) -> Dict[str, Any]:
        """
        실시간 프레임 처리 (30fps)
        캐시된 레퍼런스와 비교
        """
        if self.mode not in ['ios', 'full']:
            raise ValueError(f"실시간 처리는 'ios' 또는 'full' 모드에서만 가능합니다. 현재: {self.mode}")

        # RTMPose로 빠른 분석
        keypoints = self.wholebody.extract_wholebody_keypoints(frame)

        # 캐시된 레퍼런스와 비교
        if reference_cache:
            return self._compare_realtime(keypoints, reference_cache, frame.shape)
        else:
            return {'error': '레퍼런스 캐시가 필요합니다'}

    def analyze_with_gates(self, current_path: str, reference_path: str,
                          device_type: str = "generic",
                          test_mode: bool = True) -> Dict[str, Any]:
        """
        Gate System 기반 분석 (v6 호환 메서드)
        """
        if self.debug_mode:
            print("\n" + "="*70)
            print("[V6] Gate System 분석 시작 (개선된 여백 분석)")
            print("="*70)

            print(f"\n[입력 파일 정보]")
            print(f"  Current: {Path(current_path).name}")
            print(f"  Reference: {Path(reference_path).name}")

        # 이미지 로드
        curr_img = self._load_image(current_path)
        ref_img = self._load_image(reference_path)

        if curr_img is None or ref_img is None:
            return {'error': '이미지 로드 실패'}

        if self.debug_mode:
            print(f"\n[이미지 크기]")
            print(f"  Current: {curr_img.shape[1]}x{curr_img.shape[0]} (WxH)")
            print(f"  Reference: {ref_img.shape[1]}x{ref_img.shape[0]} (WxH)")

        # 133개 키포인트 추출
        if self.debug_mode:
            print("\n[133개 키포인트 추출]")
            print("-" * 60)

        curr_kpts = self._extract_keypoints_debug(curr_img, "Current") if self.debug_mode else \
                   self.wholebody.extract_wholebody_keypoints(curr_img)
        ref_kpts = self._extract_keypoints_debug(ref_img, "Reference") if self.debug_mode else \
                  self.wholebody.extract_wholebody_keypoints(ref_img)

        # Legacy 분석
        if self.debug_mode:
            print("\n[Legacy 시스템 분석]")
            print("-" * 60)

        legacy_result = self.legacy_comparator.compare(
            current_path=current_path,
            reference_path=reference_path,
            mode='detailed'
        )

        # Gate System 적용 (v6 Full Analysis)
        return self._full_analysis_v6(
            curr_kpts, ref_kpts,
            curr_img.shape, ref_img.shape,
            legacy_result, device_type
        )

    def _full_analysis_v6(self, curr_kpts: Dict, ref_kpts: Dict,
                         curr_shape: Tuple, ref_shape: Tuple,
                         legacy_result: Any, device_type: str) -> Dict[str, Any]:
        """
        v6 Full Analysis: 개선된 여백 분석 포함
        """
        if self.debug_mode:
            print("\n" + "="*70)
            print("[V6] Full Analysis - 개선된 Gate 점검")
            print("="*70)

        all_gates = {}

        # ============ GATE 0: 종횡비 체크 (v5와 동일) ============
        if self.debug_mode:
            print("\n[GATE 0] 종횡비 체크...")
        aspect_score, aspect_feedback = self._check_aspect_ratio_debug(curr_shape, ref_shape)
        all_gates['aspect_ratio'] = {
            'score': aspect_score,
            'passed': aspect_score >= self.gate_thresholds['aspect_ratio'],
            'feedback': aspect_feedback
        }

        # ============ GATE 1: 개선된 프레이밍 (v6) ============
        if self.debug_mode:
            print("\n[GATE 1] 프레이밍 체크 (개선된 여백 분석)...")
        framing_score, framing_result = self._check_framing_v6(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )
        all_gates['framing'] = {
            'score': framing_score,
            'passed': framing_score >= self.gate_thresholds['framing'],
            'feedback': framing_result.get('feedback', {}).get('summary', ''),
            'details': framing_result
        }

        # ============ GATE 2: 구도 (v5와 동일) ============
        if self.debug_mode:
            print("\n[GATE 2] 구도 체크...")
        composition_score, composition_feedback = self._check_composition_debug(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )
        all_gates['composition'] = {
            'score': composition_score,
            'passed': composition_score >= self.gate_thresholds['composition'],
            'feedback': composition_feedback
        }

        # ============ GATE 3: 압축감 (v5와 동일) ============
        if self.debug_mode:
            print("\n[GATE 3] 압축감 체크...")
        compression_score, compression_feedback = self._check_compression_debug(
            legacy_result, device_type
        )
        all_gates['compression'] = {
            'score': compression_score,
            'passed': compression_score >= self.gate_thresholds['compression'],
            'feedback': compression_feedback
        }

        # ============ GATE 4: 포즈 세부 (v5와 동일) ============
        if self.debug_mode:
            print("\n[GATE 4] 포즈 세부 체크...")
        pose_feedback = self._check_pose_details_debug(curr_kpts, ref_kpts)
        all_gates['pose'] = {
            'feedback': pose_feedback
        }

        # 전체 점수 계산
        scores = [g['score'] for g in all_gates.values() if 'score' in g]
        overall_score = sum(scores) / len(scores) if scores else 0

        if self.debug_mode:
            print(f"\n[최종 점수] {overall_score:.1f}/100")

        # 친절한 요약 코멘트 생성 (v6 개선)
        friendly_summary = self._generate_friendly_summary_v6(all_gates, overall_score)

        return {
            'mode': 'V6_ANALYSIS',
            'overall_score': overall_score,
            'all_gates': all_gates,
            'summary': self._generate_summary(all_gates),
            'friendly_summary': friendly_summary
        }

    def _check_framing_v6(self, curr_kpts: Dict, ref_kpts: Dict,
                         curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Dict]:
        """
        v6 프레이밍 체크 - 개선된 여백 분석 통합
        """
        if self.debug_mode:
            print("\n  [프레이밍 종합 분석 V6]")
            print("  " + "-"*50)

        # 기존 프레이밍 분석 (샷 타입, 인물 비중)
        framing_result = self.framing_analyzer.analyze_framing_comprehensive(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        # v6: 개선된 여백 분석으로 대체
        margin_analysis = self.margin_analyzer.analyze_margins_unified(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        # 기존 형식과의 호환성을 위해 변환
        framing_result['all_margins'] = convert_to_legacy_format(margin_analysis)
        framing_result['improved_margin_analysis'] = margin_analysis

        # 디버그 출력
        if self.debug_mode:
            self._print_framing_analysis_v6(framing_result, margin_analysis)

        # 점수 계산 (개선된 가중치)
        shot_score = framing_result['shot_type']['score']
        subject_score = framing_result['subject_ratio']['score']
        margin_score = margin_analysis['overall_score']

        # v6 가중치: 여백 분석의 중요도 증가
        weights = {
            'shot_type': 0.25,      # 25% (감소)
            'subject_ratio': 0.35,   # 35%
            'margins': 0.40         # 40% (증가)
        }

        overall_score = (
            shot_score * weights['shot_type'] +
            subject_score * weights['subject_ratio'] +
            margin_score * weights['margins']
        )

        framing_result['overall_score'] = overall_score

        # v6 통합 피드백
        framing_result['feedback'] = self._generate_framing_feedback_v6(
            framing_result, margin_analysis
        )

        return overall_score, framing_result

    def _print_framing_analysis_v6(self, framing_result: Dict, margin_analysis: Dict):
        """v6 프레이밍 분석 디버그 출력"""

        # 1. 샷 타입 (기존과 동일)
        shot_data = framing_result['shot_type']
        print(f"\n  [1] 샷 타입 분석")
        curr_name = shot_data['current'].get('name_kr', shot_data['current'].get('type', 'unknown'))
        ref_name = shot_data['reference'].get('name_kr', shot_data['reference'].get('type', 'unknown'))
        print(f"     Current: {curr_name}")
        print(f"     Reference: {ref_name}")
        print(f"     점수: {shot_data['score']:.0f}")

        # 2. 인물 비중 (v6 개선: 거리 우선 피드백)
        subject_data = framing_result['subject_ratio']
        print(f"\n  [2] 인물 비중")
        print(f"     Current: 화면의 {subject_data['current_ratio']*100:.1f}%")
        print(f"     Reference: 화면의 {subject_data['reference_ratio']*100:.1f}%")
        print(f"     점수: {subject_data['score']:.0f}")

        # 구체적 조정 방법 (거리 우선)
        if subject_data.get('detailed_action'):
            detail = subject_data['detailed_action']
            print(f"\n     [조정 방법]")
            print(f"       1순위: {detail['primary']}")
            print(f"       2순위: {detail['secondary']}")
            print(f"       (인물 비중 차이: {detail['ratio_diff']:.1f}%)")

        # 3. v6 통합 여백 분석
        print(f"\n  [3] 통합 여백 분석 (V6 개선)")

        # 좌우 균형
        h_analysis = margin_analysis['horizontal']
        print(f"\n     [좌우 균형]")
        curr_m = margin_analysis['current_margins']
        ref_m = margin_analysis['reference_margins']
        print(f"       Current: 좌 {curr_m['left']*100:+.0f}% | 우 {curr_m['right']*100:+.0f}%")
        print(f"       Reference: 좌 {ref_m['left']*100:+.0f}% | 우 {ref_m['right']*100:+.0f}%")
        print(f"       상태: {h_analysis['status']} (점수: {h_analysis['score']:.0f})")
        if h_analysis.get('out_of_frame_warning'):
            print(f"       ⚠️ {h_analysis['out_of_frame_warning']}")

        # 상하 균형
        v_analysis = margin_analysis['vertical']
        print(f"\n     [상하 균형]")
        print(f"       Current: 상 {curr_m['top']*100:+.0f}% | 하 {curr_m['bottom']*100:+.0f}%")
        print(f"       Reference: 상 {ref_m['top']*100:+.0f}% | 하 {ref_m['bottom']*100:+.0f}%")

        # 인물 위치 정보
        curr_pos = v_analysis.get('current_position', 0.5)
        ref_pos = v_analysis.get('reference_position', 0.5)
        print(f"       인물 위치: Current {curr_pos:.2f} vs Reference {ref_pos:.2f} (0=상단, 1=하단)")

        # 하이앵글 감지
        v_details = v_analysis.get('details', {})
        if v_details.get('current_is_high_angle'):
            print(f"       ⚡ 하이앵글 감지 (위에서 내려다봄)")

        print(f"       상태: {v_analysis['status']} (점수: {v_analysis['score']:.0f})")
        if v_analysis.get('out_of_frame_warning'):
            print(f"       ⚠️ {v_analysis['out_of_frame_warning']}")

        # 조정 방법 (개선됨)
        if v_analysis.get('adjustment'):
            adj = v_analysis['adjustment']
            if adj['direction'] == 'lower_camera':
                print(f"       💡 {adj['camera_action']}")
            elif adj['direction'] == 'tilt_down':
                print(f"       💡 {adj['camera_action']}")
            elif adj['direction'] == 'tilt_up':
                print(f"       💡 {adj['camera_action']}")

        # 하단 특별 분석
        bottom_special = margin_analysis['bottom_special']
        if bottom_special.get('special_message'):
            print(f"\n     [하단 특별 상황]")
            print(f"       {bottom_special['special_message']}")

        # 통합 여백 점수
        print(f"\n     [여백 종합 점수] {margin_analysis['overall_score']:.0f}/100")

        # 4. 프레이밍 종합 조정 방법
        self._print_framing_adjustments(framing_result, margin_analysis)

    def _print_framing_adjustments(self, framing_result: Dict, margin_analysis: Dict):
        """프레이밍 종합 조정 방법 출력"""

        adjustments = []

        # 샷 타입 불일치
        shot_data = framing_result.get('shot_type', {})
        if not shot_data.get('same_category'):
            curr = shot_data.get('current', {}).get('name_kr', '')
            ref = shot_data.get('reference', {}).get('name_kr', '')
            adjustments.append({
                'priority': 1,
                'type': 'shot_type',
                'message': f"샷 타입 변경: {curr} → {ref}"
            })

        # 인물 비중 조정
        subject_data = framing_result.get('subject_ratio', {})
        if subject_data.get('detailed_action'):
            detail = subject_data['detailed_action']
            adjustments.append({
                'priority': 2 if len(adjustments) > 0 else 1,
                'type': 'subject_size',
                'message': detail['primary']
            })

        # 여백 조정
        actionable = margin_analysis.get('actionable_feedback', {})
        if actionable.get('primary_action'):
            action = actionable['primary_action']
            priority = len(adjustments) + 1

            if action['type'] == 'horizontal_move':
                message = action['camera']
            elif action['type'] == 'vertical_tilt':
                message = action['camera']
            elif action['type'] == 'bottom_adjustment':
                message = action['message']
            else:
                message = "여백 조정 필요"

            adjustments.append({
                'priority': priority,
                'type': 'margin',
                'message': message
            })

        # 출력
        if adjustments:
            print(f"\n  [프레이밍 조정 방법]")
            print("  " + "-"*50)

            # 우선순위 정렬
            adjustments.sort(key=lambda x: x['priority'])

            for adj in adjustments[:3]:  # 최대 3개
                print(f"     {adj['priority']}순위: {adj['message']}")

            # 추가 팁
            if len(adjustments) > 1:
                print(f"\n     💡 팁: 1순위부터 순서대로 조정하면서 확인하세요")

    def _generate_framing_feedback_v6(self, framing_result: Dict,
                                      margin_analysis: Dict) -> Dict:
        """v6 통합 프레이밍 피드백 생성"""

        actions = []
        issues = []
        severity = 'minor'

        # 1. 샷 타입 이슈
        shot_data = framing_result['shot_type']
        if not shot_data['same_category']:
            issues.append('shot_type_mismatch')
            severity = 'major'
            curr_type = shot_data['current'].get('name_kr', '')
            ref_type = shot_data['reference'].get('name_kr', '')
            actions.append(f"샷 타입 변경: {curr_type} → {ref_type}")

        # 2. 인물 비중 이슈
        subject_data = framing_result['subject_ratio']
        if subject_data['action']:
            issues.append('subject_ratio')
            actions.append(subject_data['action'])

        # 3. v6 여백 이슈
        margin_feedback = margin_analysis['actionable_feedback']
        if margin_feedback.get('has_issues'):
            issues.append('margin_imbalance')
            # 주요 조정만 추가
            if margin_feedback.get('primary_action'):
                action = margin_feedback['primary_action']
                if action['type'] == 'horizontal_move':
                    actions.append(action['camera'])
                elif action['type'] == 'vertical_tilt':
                    actions.append(action['camera'])
                elif action['type'] == 'bottom_adjustment':
                    actions.append(action['message'])

        # 종합 평가
        if not issues:
            summary = "프레이밍이 레퍼런스와 거의 동일합니다!"
            severity = 'excellent'
        elif len(issues) == 1:
            summary = "프레이밍 미세 조정이 필요합니다"
            severity = 'minor'
        elif len(issues) == 2:
            summary = "프레이밍 조정이 필요합니다"
            severity = 'moderate'
        else:
            summary = "프레이밍이 레퍼런스와 차이가 있습니다"
            severity = 'major'

        # 친절한 메시지
        friendly_message = self._create_friendly_framing_message_v6(
            shot_data, subject_data, margin_analysis
        )

        return {
            'issues': issues,
            'actions': actions[:3],  # 최대 3개
            'summary': summary,
            'severity': severity,
            'friendly_message': friendly_message
        }

    def _create_friendly_framing_message_v6(self, shot: Dict, subject: Dict,
                                           margin_analysis: Dict) -> str:
        """v6 친절한 프레이밍 메시지"""

        messages = []

        # 샷 타입
        if shot['same_category']:
            if shot['score'] >= 90:
                messages.append("샷 타입이 일치합니다")
        else:
            curr = shot['current'].get('name_kr', '')
            ref = shot['reference'].get('name_kr', '')
            messages.append(f"샷 타입 조정 필요 ({curr} → {ref})")

        # 인물 크기 (v6 개선: 구체적 거리)
        if subject['direction'] == 'smaller':
            if subject.get('detailed_action'):
                detail = subject['detailed_action']
                messages.append(detail['primary'])
            else:
                messages.append("인물을 더 크게 담아주세요")
        elif subject['direction'] == 'larger':
            if subject.get('detailed_action'):
                detail = subject['detailed_action']
                messages.append(detail['primary'])
            else:
                messages.append("인물을 더 작게 담아주세요")

        # 여백 문제 (v6)
        actionable = margin_analysis['actionable_feedback']
        if actionable.get('has_issues') and actionable.get('message'):
            # 첫 번째 줄만 추가 (간결하게)
            first_line = actionable['message'].split('\n')[0]
            if first_line and '조정' in first_line:
                messages.append(first_line)

        return ". ".join(messages) if messages else "프레이밍이 적절합니다"

    def _generate_friendly_summary_v6(self, all_gates: Dict, overall_score: float) -> str:
        """v6 친절한 요약 코멘트 생성"""

        passed = []
        failed = []

        # 구체적 조정 방법 수집
        specific_actions = []

        for gate_name, gate_data in all_gates.items():
            if 'passed' in gate_data:
                if gate_data['passed']:
                    if gate_name == 'aspect_ratio':
                        passed.append('종횡비')
                    elif gate_name == 'framing':
                        passed.append('프레이밍')
                    elif gate_name == 'composition':
                        passed.append('구도')
                    elif gate_name == 'compression':
                        passed.append('압축감')
                else:
                    if gate_name == 'aspect_ratio':
                        failed.append('종횡비')
                    elif gate_name == 'framing':
                        failed.append('프레이밍')
                        # v6: 개선된 여백 분석에서 구체적 조정 추출
                        if 'details' in gate_data and 'improved_margin_analysis' in gate_data['details']:
                            margin_feedback = gate_data['details']['improved_margin_analysis']['actionable_feedback']
                            if margin_feedback.get('primary_action'):
                                action = margin_feedback['primary_action']
                                if action.get('camera'):
                                    specific_actions.append(action['camera'])
                    elif gate_name == 'composition':
                        failed.append('구도')
                    elif gate_name == 'compression':
                        failed.append('압축감')

        # 메시지 생성 (v6 개선)
        if overall_score >= 95:
            return "거의 완벽합니다! 레퍼런스와 매우 유사해요."
        elif overall_score >= 85:
            if len(failed) == 1:
                if specific_actions:
                    return f"레퍼런스와 비슷합니다. {specific_actions[0]}하면 더 좋아질 거예요."
                else:
                    return f"레퍼런스와 비슷합니다. {failed[0]}만 조정하면 더 좋아질 거예요."
            else:
                return "레퍼런스와 비슷하지만 미세 조정이 필요합니다."
        elif overall_score >= 75:
            if specific_actions:
                return f"전반적으로 괜찮지만, {specific_actions[0]}가 필요해요."
            elif len(passed) >= 2:
                return f"{', '.join(passed)}은(는) 잘 맞지만, {', '.join(failed)}은(는) 조정이 필요해요."
            else:
                return "전반적으로 괜찮지만 몇 가지 개선이 필요합니다."
        elif overall_score >= 65:
            if specific_actions:
                return f"레퍼런스와 차이가 있으니 {specific_actions[0]}가 필요합니다."
            else:
                return "레퍼런스와 차이가 있으니 조정이 필요합니다."
        else:
            if specific_actions:
                return f"상당한 차이가 있어요. 먼저 {specific_actions[0]}해 보세요."
            else:
                return "상당한 차이가 있어 단계적 조정이 필요해요."

    # ========== 이하 v5와 동일한 함수들 ==========

    def _extract_keypoints_debug(self, img: np.ndarray, label: str) -> Dict:
        """키포인트 추출 (v5와 동일)"""
        if self.debug_mode:
            print(f"\n[{label} 이미지 키포인트 분석]")

        kpts = self.wholebody.extract_wholebody_keypoints(img)

        if self.debug_mode:
            print(f"  인물 수: {kpts['num_persons']}명")

            if kpts['num_persons'] > 0:
                body_kpts = kpts.get('body_keypoints', {})
                print(f"\n  [신체 키포인트] {len(body_kpts)}개 검출")

                key_parts = ['nose', 'left_shoulder', 'right_shoulder',
                           'left_hip', 'right_hip', 'left_knee', 'right_knee',
                           'left_ankle', 'right_ankle']

                for part in key_parts[:3]:  # 간략히 3개만
                    if part in body_kpts:
                        pos = body_kpts[part]['position']
                        conf = body_kpts[part].get('confidence', 0)
                        print(f"    {part:15s}: ({pos[0]:4.0f}, {pos[1]:4.0f}) 신뢰도={conf:.2f}")

        return kpts

    def _check_aspect_ratio_debug(self, curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """종횡비 체크 (v6 개선: 정확한 비율 표시)"""
        # shape는 (height, width) 순서
        curr_ratio = curr_shape[1] / curr_shape[0]  # width / height
        ref_ratio = ref_shape[1] / ref_shape[0]

        def get_ratio_name(ratio):
            """종횡비를 이름으로 변환 (너비:높이 형식)"""
            if abs(ratio - 1.0) < 0.1:
                return "1:1 (정사각형)"
            elif abs(ratio - 1.33) < 0.1:
                return "4:3 (가로)"
            elif abs(ratio - 1.5) < 0.1:
                return "3:2 (가로 DSLR)"
            elif abs(ratio - 1.78) < 0.1:
                return "16:9 (가로 와이드)"
            elif abs(ratio - 0.75) < 0.1:
                return "3:4 (세로)"  # 0.75 = 3/4 = 너비 3, 높이 4
            elif abs(ratio - 0.67) < 0.1:
                return "2:3 (세로 DSLR)"
            elif abs(ratio - 0.56) < 0.1:
                return "9:16 (세로 와이드)"
            else:
                # 기본값
                if ratio > 1:
                    return f"{ratio:.2f}:1 (가로)"
                else:
                    return f"1:{(1/ratio):.2f} (세로)"

        curr_name = get_ratio_name(curr_ratio)
        ref_name = get_ratio_name(ref_ratio)

        if self.debug_mode:
            print(f"  Current 이미지: {curr_shape[1]}x{curr_shape[0]} (WxH)")
            print(f"    종횡비: {curr_ratio:.3f} = {curr_name}")
            print(f"  Reference 이미지: {ref_shape[1]}x{ref_shape[0]} (WxH)")
            print(f"    종횡비: {ref_ratio:.3f} = {ref_name}")

        diff = abs(curr_ratio - ref_ratio)

        if diff < 0.1:
            if self.debug_mode:
                print(f"  -> 종횡비 일치")
            return 100, None

        score = max(30, 100 - (diff * 100))

        if self.debug_mode:
            print(f"  -> 종횡비 불일치 (점수: {score:.0f})")
            print(f"  📐 조정 방법: {ref_name}로 비율을 변경하세요")

            # 구체적인 변경 방법 제안
            if "16:9" in ref_name and "4:3" in curr_name:
                print(f"     카메라 설정에서 16:9 와이드스크린으로 변경")
            elif "4:3" in ref_name and "16:9" in curr_name:
                print(f"     카메라 설정에서 4:3 표준 비율로 변경")
            elif "1:1" in ref_name:
                print(f"     카메라 설정에서 정사각형(1:1)으로 변경")
            elif "9:16" in ref_name or "3:4" in ref_name:
                print(f"     세로 모드로 촬영하고 {ref_name} 비율로 설정")

        return score, {
            'issue': 'ASPECT_RATIO_MISMATCH',
            'diff': diff,
            'current_name': curr_name,
            'target_name': ref_name,
            'action': f"{ref_name}로 비율을 변경하세요"
        }

    def _check_composition_debug(self, curr_kpts: Dict, ref_kpts: Dict,
                                curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """구도 체크 (v5와 동일)"""
        if self.debug_mode:
            print("\n  [구도 분석]")

        curr_center = self._calculate_face_center(curr_kpts, curr_shape)
        ref_center = self._calculate_face_center(ref_kpts, ref_shape)

        if not curr_center or not ref_center:
            return 75, None

        curr_grid = self._to_grid_position(curr_center)
        ref_grid = self._to_grid_position(ref_center)

        if self.debug_mode:
            print(f"  Current 얼굴: ({curr_center[0]:.2f}, {curr_center[1]:.2f}) → {curr_grid}")
            print(f"  Reference 얼굴: ({ref_center[0]:.2f}, {ref_center[1]:.2f}) → {ref_grid}")

        if curr_grid == ref_grid:
            if self.debug_mode:
                print(f"  -> 구도 일치")
            return 90, None

        distance = math.sqrt((curr_center[0] - ref_center[0])**2 +
                           (curr_center[1] - ref_center[1])**2)
        score = max(40, 80 - (distance * 100))

        if self.debug_mode:
            print(f"  -> 구도 불일치 (점수: {score:.0f})")

        return score, {
            'issue': 'POSITION_MISMATCH',
            'current_grid': curr_grid,
            'target_grid': ref_grid
        }

    def _check_compression_debug(self, legacy_result: Any, device_type: str) -> Tuple[float, Optional[Dict]]:
        """압축감 체크 (v6 개선: 광각/망원 감지 + 구체적 조정)"""
        if self.debug_mode:
            print("\n  [압축감 분석]")

        if not hasattr(legacy_result, 'detailed_feedback'):
            return 80, None

        if 'compression' not in legacy_result.detailed_feedback:
            return 80, None

        comp_data = legacy_result.detailed_feedback['compression']

        import re
        curr_match = re.search(r'\(([0-9.]+)\)', comp_data.get('current', ''))
        ref_match = re.search(r'\(([0-9.]+)\)', comp_data.get('reference', ''))

        if not (curr_match and ref_match):
            return 80, None

        curr_comp = float(curr_match.group(1))
        ref_comp = float(ref_match.group(1))

        def describe_lens_type(value):
            """렌즈 타입 판별"""
            if value < 0.3:
                return "광각렌즈", "wide"
            elif value < 0.45:
                return "준광각", "semi-wide"
            elif value < 0.6:
                return "표준렌즈", "normal"
            elif value < 0.75:
                return "중망원", "medium-tele"
            else:
                return "망원렌즈", "telephoto"

        curr_lens, curr_type = describe_lens_type(curr_comp)
        ref_lens, ref_type = describe_lens_type(ref_comp)

        if self.debug_mode:
            print(f"  Current: {curr_comp:.2f} ({curr_lens})")
            print(f"  Reference: {ref_comp:.2f} ({ref_lens})")

        diff = abs(ref_comp - curr_comp)

        if diff < 0.05:
            if self.debug_mode:
                print(f"  -> 압축감 일치")
            return 95, None

        # 점수 계산
        if diff < 0.2:
            score = 95 - (diff - 0.05) * 100
        elif diff < 0.4:
            score = 80 - (diff - 0.2) * 75
        else:
            score = max(50, 65 - (diff - 0.4) * 50)

        # 구체적 조정 방법 생성
        adjustment_message = self._generate_compression_adjustment(
            curr_comp, ref_comp, curr_lens, ref_lens
        )

        if self.debug_mode:
            print(f"  -> 압축감 차이 (점수: {score:.0f})")
            print(f"\n  📷 조정 방법:")
            for line in adjustment_message.split('\n'):
                if line.strip():
                    print(f"     {line.strip()}")

        return score, {
            'issue': 'COMPRESSION_MISMATCH',
            'current_compression': curr_comp,
            'target_compression': ref_comp,
            'current_lens': curr_lens,
            'target_lens': ref_lens,
            'adjustment': adjustment_message
        }

    def _generate_compression_adjustment(self, curr_comp: float, ref_comp: float,
                                        curr_lens: str, ref_lens: str) -> str:
        """압축감 조정 메시지 생성"""

        messages = []

        if curr_comp < ref_comp:  # 현재가 더 광각
            diff_level = ref_comp - curr_comp

            if diff_level < 0.15:
                messages.append(f"현재 사진이 레퍼런스보다 약간 더 광각입니다 (압축감 {curr_comp:.2f} vs {ref_comp:.2f})")
                messages.append("한두 걸음 뒤로 물러난 뒤, 줌을 한 단계 키워서 촬영하면")
                messages.append("배경이 조금 더 당겨지고, 레퍼런스에 가까운 압축감을 만들 수 있습니다")
            elif diff_level < 0.3:
                messages.append(f"현재 {curr_lens}로 촬영되어 레퍼런스({ref_lens})보다 광각입니다")
                messages.append("몇 걸음 뒤로 물러나서 줌을 2-3단계 키우거나")
                messages.append("더 긴 초점거리의 렌즈를 사용하세요")
                messages.append("배경이 피사체와 가까워 보이는 효과를 만들 수 있습니다")
            else:
                messages.append(f"상당한 압축감 차이가 있습니다 ({curr_lens} → {ref_lens})")
                messages.append("여러 걸음 뒤로 물러나서 최대한 줌인하거나")
                messages.append("망원 렌즈로 교체하여 촬영하세요")

        else:  # 현재가 더 망원
            diff_level = curr_comp - ref_comp

            if diff_level < 0.15:
                messages.append(f"현재 사진이 레퍼런스보다 약간 더 압축되어 있습니다 (압축감 {curr_comp:.2f} vs {ref_comp:.2f})")
                messages.append("한두 걸음 앞으로 다가간 뒤, 줌을 한 단계 줄여서 촬영하면")
                messages.append("배경이 조금 더 넓어지고, 레퍼런스에 가까운 느낌을 만들 수 있습니다")
            elif diff_level < 0.3:
                messages.append(f"현재 {curr_lens}로 촬영되어 레퍼런스({ref_lens})보다 압축감이 강합니다")
                messages.append("몇 걸음 앞으로 다가가서 줌을 2-3단계 줄이거나")
                messages.append("더 짧은 초점거리의 렌즈를 사용하세요")
                messages.append("배경이 더 넓고 공간감 있게 보일 것입니다")
            else:
                messages.append(f"상당한 압축감 차이가 있습니다 ({curr_lens} → {ref_lens})")
                messages.append("여러 걸음 앞으로 다가가서 줌아웃하거나")
                messages.append("광각 렌즈로 교체하여 촬영하세요")

        return "\n".join(messages)

    def _check_pose_details_debug(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[List[Dict]]:
        """포즈 세부 체크 (v5와 동일)"""
        if self.debug_mode:
            print("\n  [포즈 세부 분석]")

        minor_adjustments = []
        curr_body = curr_kpts.get('body_keypoints', {})

        # 어깨 정렬 체크
        if 'left_shoulder' in curr_body and 'right_shoulder' in curr_body:
            curr_left = curr_body['left_shoulder']['position']
            curr_right = curr_body['right_shoulder']['position']

            dx = curr_right[0] - curr_left[0]
            dy = curr_right[1] - curr_left[1]
            angle_deg = math.degrees(math.atan2(dy, dx))

            if abs(angle_deg) > 90:
                deviation = abs(abs(angle_deg) - 180)
            else:
                deviation = abs(angle_deg)

            if self.debug_mode:
                print(f"  어깨 기울기: {deviation:.1f}도")

            if deviation > 20:
                minor_adjustments.append({
                    'category': 'posture',
                    'importance': 'optional',
                    'suggestion': f"어깨가 기울어져 있습니다 ({deviation:.1f}도)"
                })

        return minor_adjustments if minor_adjustments else None

    def _generate_integrated_feedback_v6(self, all_gates: Dict) -> Optional[Dict]:
        """
        V6 통합 피드백 생성
        모든 분석 결과를 종합하여 하나의 실행 가능한 지시 생성
        """
        framing_gate = all_gates.get('framing', {})
        compression_gate = all_gates.get('compression', {})

        if not framing_gate.get('details'):
            return None

        framing_details = framing_gate['details']
        subject_data = framing_details.get('subject_ratio', {})
        margin_analysis = framing_details.get('improved_margin_analysis', {})
        compression_feedback = compression_gate.get('feedback')

        # 문제 수집
        problems = []

        # 1. 인물 크기
        if subject_data.get('direction') == 'smaller':
            detailed = subject_data.get('detailed_action', {})
            problems.append({
                'type': 'subject_small',
                'priority': 1,
                'ratio_diff': detailed.get('ratio_diff', 0),
                'distance': self._estimate_distance(detailed.get('ratio_diff', 0))
            })
        elif subject_data.get('direction') == 'larger':
            detailed = subject_data.get('detailed_action', {})
            problems.append({
                'type': 'subject_large',
                'priority': 1,
                'ratio_diff': detailed.get('ratio_diff', 0),
                'distance': self._estimate_distance(detailed.get('ratio_diff', 0))
            })

        # 2. 상하 여백
        v_analysis = margin_analysis.get('vertical', {})
        if v_analysis.get('adjustment'):
            adj = v_analysis['adjustment']
            problems.append({
                'type': 'vertical_position',
                'priority': 2,
                'adjustment': adj,
                'is_high_angle': adj.get('is_high_angle', False)
            })

        # 3. 좌우 여백
        h_analysis = margin_analysis.get('horizontal', {})
        if h_analysis.get('adjustment'):
            problems.append({
                'type': 'horizontal_position',
                'priority': 3,
                'adjustment': h_analysis['adjustment']
            })

        # 4. 압축감
        if compression_feedback and compression_feedback.get('issue'):
            problems.append({
                'type': 'compression',
                'priority': 4,
                'feedback': compression_feedback
            })

        if not problems:
            return None

        # 우선순위 정렬
        problems.sort(key=lambda x: x['priority'])

        # 통합 지시 생성
        return self._create_unified_instruction(problems, subject_data, v_analysis, h_analysis)

    def _estimate_distance(self, ratio_diff: float) -> str:
        """비율 차이를 거리로 변환"""
        if ratio_diff < 10:
            return "한 걸음"
        elif ratio_diff < 20:
            return "두세 걸음"
        else:
            return "여러 걸음"

    def _create_unified_instruction(self, problems: List[Dict],
                                   subject_data: Dict, v_analysis: Dict,
                                   h_analysis: Dict) -> Dict:
        """
        통합 실행 지시 생성
        """
        # 주요 문제 파악
        has_size_issue = any(p['type'] in ['subject_small', 'subject_large'] for p in problems)
        has_vertical_issue = any(p['type'] == 'vertical_position' for p in problems)
        has_horizontal_issue = any(p['type'] == 'horizontal_position' for p in problems)

        # 단일 지시 생성
        instructions = []
        step_by_step = []
        expected_results = []

        # 1. 전후 이동 (인물 크기)
        if has_size_issue:
            size_problem = next(p for p in problems if p['type'] in ['subject_small', 'subject_large'])

            if size_problem['type'] == 'subject_small':
                distance = size_problem['distance']
                instructions.append(f"피사체 쪽으로 {distance} 이동")
                step_by_step.append(f"카메라를 피사체 쪽으로 {distance} 앞으로 이동")
                expected_results.append("인물이 화면을 더 많이 채움")

                # 상하 조정과 통합
                if has_vertical_issue:
                    v_problem = next(p for p in problems if p['type'] == 'vertical_position')
                    adj = v_problem['adjustment']

                    if adj['direction'] == 'lower_camera' and adj.get('is_high_angle'):
                        # 하이앵글 + 인물 작음 → 앞으로 가면서 카메라를 내리고 평행하게
                        instructions[0] = f"피사체 쪽으로 {distance} 이동하면서 카메라를 아래로 내리기"
                        step_by_step.append("동시에 카메라 높이를 낮추고 앵글을 평행하게 조정")
                        expected_results.append("인물이 화면 중앙으로 이동")
                    elif adj['direction'] == 'tilt_down':
                        instructions[0] = f"피사체 쪽으로 {distance} 이동하면서 카메라를 아래로 틸트"
                        step_by_step.append(f"동시에 카메라를 {adj['angle']}도 아래로 틸트")
                        expected_results.append("인물이 화면 중앙으로 이동")

            else:  # subject_large
                distance = size_problem['distance']
                instructions.append(f"피사체에서 {distance} 뒤로 이동")
                step_by_step.append(f"카메라를 피사체에서 {distance} 뒤로 이동")
                expected_results.append("인물 크기가 적절해짐")

        # 2. 좌우 이동 (별도로 필요한 경우만)
        if has_horizontal_issue and not (has_size_issue and has_vertical_issue):
            h_problem = next(p for p in problems if p['type'] == 'horizontal_position')
            adj = h_problem['adjustment']
            step_by_step.append(f"추가로 {adj['camera_action']}")

        # 주요 지시문 생성
        if instructions:
            primary = instructions[0]
        else:
            primary = "현재 구도가 적절합니다"

        return {
            'has_issues': len(problems) > 0,
            'primary_instruction': primary,
            'step_by_step': step_by_step,
            'expected_result': expected_results,
            'problems_detected': [p['type'] for p in problems]
        }

    def _generate_summary(self, all_gates: Dict) -> str:
        """전체 분석 요약 생성 (v5와 동일)"""
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

    def _load_image(self, path: str) -> Optional[np.ndarray]:
        """이미지 로드 (v5와 동일)"""
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
        """얼굴 중심 계산 (v5와 동일)"""
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
        """3분할 구도 위치 변환 (v5와 동일)"""
        grid_x = min(int(pos[0] * 3) + 1, 3)
        grid_y = min(int(pos[1] * 3) + 1, 3)
        return (grid_x, grid_y)


def main():
    """메인 실행 함수"""

    try:
        print("\n" + "="*70)
        print("  TryAngle v6 - 개선된 여백 분석  ")
        print("="*70)

        # 시스템 초기화 (v6)
        feedback_system = SmartFeedbackV6(language='ko', debug_mode=True)

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

        # 친절한 요약
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
            print("\nv6 분석을 종료합니다.")

    except KeyboardInterrupt:
        print("\n\n종료합니다...")
    except Exception as e:
        print(f"\n오류: {e}")
        traceback.print_exc()

    # =================== v7 추가 메서드 ===================

    def _analyze_reference_fast(self, reference_path: str) -> Dict[str, Any]:
        """
        빠른 레퍼런스 분석 (Legacy 없이)
        RTMPose만 사용하여 iOS에서 빠르게 분석
        """
        ref_img = self._load_image(reference_path)
        if ref_img is None:
            return {'error': '레퍼런스 이미지 로드 실패'}

        # RTMPose 키포인트 추출
        ref_kpts = self.wholebody.extract_wholebody_keypoints(ref_img)

        # 여백 분석 (RTMPose 기반)
        margin_result = self.margin_analyzer.analyze_margins_unified(
            ref_kpts, ref_kpts,  # 자기 자신과 비교
            ref_img.shape, ref_img.shape
        )

        # 프레이밍 분석
        framing_result = self.framing_analyzer.analyze(ref_kpts, ref_img.shape)

        return {
            'keypoints': ref_kpts,
            'margins': margin_result['current_margins'],
            'framing': framing_result,
            'image_shape': ref_img.shape,
            'mode': 'fast',
            'timestamp': time.time()
        }

    def _analyze_reference_full(self, reference_path: str) -> Dict[str, Any]:
        """
        완전한 레퍼런스 분석 (Legacy 사용)
        Grounding DINO + Depth Anything 포함
        """
        # Legacy 시스템으로 정밀 분석
        legacy_result = self.legacy_comparator.analyze_image(reference_path)

        # RTMPose 키포인트도 추출
        ref_img = self._load_image(reference_path)
        ref_kpts = self.wholebody.extract_wholebody_keypoints(ref_img)

        return {
            'keypoints': ref_kpts,
            'legacy_analysis': legacy_result,
            'margins': {
                'top': legacy_result.margins[0],
                'right': legacy_result.margins[1],
                'bottom': legacy_result.margins[2],
                'left': legacy_result.margins[3]
            },
            'compression': legacy_result.compression_index,
            'person_bbox': legacy_result.person_bbox,
            'image_shape': ref_img.shape,
            'mode': 'full',
            'timestamp': time.time()
        }

    def _compare_realtime(self, curr_kpts: Dict, ref_cache: Dict, curr_shape: Tuple) -> Dict[str, Any]:
        """
        실시간 비교 (캐시된 레퍼런스와)
        """
        ref_kpts = ref_cache['keypoints']
        ref_shape = ref_cache['image_shape']

        # 여백 분석
        margin_result = self.margin_analyzer.analyze_margins_unified(
            curr_kpts, ref_kpts,
            curr_shape, ref_shape
        )

        # 프레이밍 분석
        framing_result = self.framing_analyzer.analyze(curr_kpts, curr_shape)

        # 간단한 피드백 생성
        feedback = self._generate_realtime_feedback(
            margin_result, framing_result, ref_cache
        )

        return {
            'margins': margin_result,
            'framing': framing_result,
            'feedback': feedback,
            'processing_time': time.time() - ref_cache['timestamp']
        }

    def _generate_realtime_feedback(self, margin_result: Dict, framing_result: Dict, ref_cache: Dict) -> str:
        """
        실시간 피드백 생성 (간단하고 직관적)
        """
        feedbacks = []

        # 여백 피드백
        if margin_result['actionable_feedback']:
            if margin_result['actionable_feedback'].get('horizontal'):
                h_feedback = margin_result['actionable_feedback']['horizontal']
                if '왼쪽' in h_feedback:
                    feedbacks.append("← 왼쪽으로")
                elif '오른쪽' in h_feedback:
                    feedbacks.append("→ 오른쪽으로")

            if margin_result['actionable_feedback'].get('vertical'):
                v_feedback = margin_result['actionable_feedback']['vertical']
                if '위로' in v_feedback or '올려' in v_feedback:
                    feedbacks.append("↑ 위로")
                elif '아래' in v_feedback or '내려' in v_feedback:
                    feedbacks.append("↓ 아래로")

        # 프레이밍 피드백
        if framing_result and 'subject_ratio' in framing_result:
            ratio = framing_result['subject_ratio']
            if ratio < 0.3:
                feedbacks.append("🔍 가까이")
            elif ratio > 0.6:
                feedbacks.append("🔍 멀리")

        # 최대 2개 피드백만 표시
        if feedbacks:
            return " | ".join(feedbacks[:2])
        else:
            return "✓ 좋아요"


if __name__ == "__main__":
    # v7 테스트용 main은 따로 작성 필요
    print("[SmartFeedbackV7] 테스트는 tests/test_realtime.py를 사용하세요")