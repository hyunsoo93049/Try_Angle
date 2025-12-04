#!/usr/bin/env python3
"""
TryAngle v1.5 - Smart Feedback v5
Gate System with Full Analysis Mode
- 종횡비 체크 추가
- test_mode: 모든 Gate 분석 결과 표시
- production_mode: 단계별 차단
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

# Framing Analyzer 임포트
from framing_analyzer import FramingAnalyzer

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


class SmartFeedbackV5:
    """
    Gate System v5: 종횡비 체크 + Full Analysis Mode
    """

    def __init__(self, language='ko'):
        """초기화"""
        print(f"[SmartFeedbackV5] 초기화 중... (언어: {language})")

        # 133개 키포인트 분석기
        self.wholebody = RTMPoseWholebodyAnalyzer(mode='balanced')

        # Legacy 시스템 (v2 압축감 로직)
        self.legacy_comparator = ReferenceComparison()

        # 프레이밍 분석기
        self.framing_analyzer = FramingAnalyzer()

        # 언어 설정
        self.config = get_config(language)
        self.language = language

        # Gate 통과 기준
        self.gate_thresholds = {
            'aspect_ratio': 90,    # 종횡비 일치도
            'framing': 70,         # 프레이밍
            'composition': 75,     # 구도
            'compression': 80      # 압축감
        }

        # 디바이스별 줌 시스템
        self.device_zoom_systems = {
            "iPhone": [0.5, 1.0, 2.0, 3.0, 5.0],
            "Galaxy": [0.6, 1.0, 3.0, 10.0],
            "generic": [0.5, 1.0, 2.0, 3.0, 5.0]
        }

        print("[SmartFeedbackV5] 초기화 완료")

    def analyze_with_gates(self, current_path: str, reference_path: str,
                          device_type: str = "generic",
                          test_mode: bool = False) -> Dict[str, Any]:
        """
        Gate System 기반 분석

        Args:
            current_path: 현재 이미지 경로
            reference_path: 레퍼런스 이미지 경로
            device_type: 디바이스 타입
            test_mode: True면 모든 Gate 분석, False면 단계별 차단

        Returns:
            전체 분석 결과
        """
        print("\n[Gate System v5] 분석 시작")
        print(f"모드: {'테스트 (모든 Gate 분석)' if test_mode else '프로덕션 (단계별 차단)'}")
        print("-" * 60)

        # 이미지 로드
        curr_img = self._load_image(current_path)
        ref_img = self._load_image(reference_path)

        if curr_img is None or ref_img is None:
            return {'error': '이미지 로드 실패'}

        # 133개 키포인트 추출
        print("\n[1/2] 133개 키포인트 추출...")
        curr_kpts = self.wholebody.extract_wholebody_keypoints(curr_img)
        ref_kpts = self.wholebody.extract_wholebody_keypoints(ref_img)

        print(f"   현재: {curr_kpts['num_persons']}명 감지")
        print(f"   레퍼런스: {ref_kpts['num_persons']}명 감지")

        # Legacy 분석
        print("\n[2/2] Legacy 시스템 분석...")
        legacy_result = self.legacy_comparator.compare(
            current_path=current_path,
            reference_path=reference_path,
            mode='detailed'
        )

        # Gate System 적용
        if test_mode:
            return self._full_analysis_mode(
                curr_kpts, ref_kpts,
                curr_img.shape, ref_img.shape,
                legacy_result, device_type
            )
        else:
            return self._production_mode(
                curr_kpts, ref_kpts,
                curr_img.shape, ref_img.shape,
                legacy_result, device_type
            )

    def _full_analysis_mode(self, curr_kpts: Dict, ref_kpts: Dict,
                           curr_shape: Tuple, ref_shape: Tuple,
                           legacy_result: Any, device_type: str) -> Dict[str, Any]:
        """
        테스트 모드: 모든 Gate 분석 수행
        """
        print("\n[Full Analysis Mode] 모든 Gate 점검")

        all_gates = {}

        # ============ GATE 0: 종횡비 체크 ============
        print("\n[GATE 0] 종횡비 체크...")
        aspect_score, aspect_feedback = self._check_aspect_ratio(curr_shape, ref_shape)
        all_gates['aspect_ratio'] = {
            'score': aspect_score,
            'passed': aspect_score >= self.gate_thresholds['aspect_ratio'],
            'feedback': aspect_feedback
        }
        print(f"   점수: {aspect_score:.0f} ({'통과' if all_gates['aspect_ratio']['passed'] else '실패'})")

        # ============ GATE 1: 프레이밍 ============
        print("\n[GATE 1] 프레이밍 체크...")
        framing_score, framing_feedback = self._check_framing(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )
        all_gates['framing'] = {
            'score': framing_score,
            'passed': framing_score >= self.gate_thresholds['framing'],
            'feedback': framing_feedback
        }
        print(f"   점수: {framing_score:.0f} ({'통과' if all_gates['framing']['passed'] else '실패'})")

        # ============ GATE 2: 구도 ============
        print("\n[GATE 2] 구도 체크...")
        composition_score, composition_feedback = self._check_composition(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )
        all_gates['composition'] = {
            'score': composition_score,
            'passed': composition_score >= self.gate_thresholds['composition'],
            'feedback': composition_feedback
        }
        print(f"   점수: {composition_score:.0f} ({'통과' if all_gates['composition']['passed'] else '실패'})")

        # ============ GATE 3: 압축감 ============
        print("\n[GATE 3] 압축감 체크...")
        compression_score, compression_feedback = self._check_compression(
            legacy_result, device_type
        )
        all_gates['compression'] = {
            'score': compression_score,
            'passed': compression_score >= self.gate_thresholds['compression'],
            'feedback': compression_feedback
        }
        print(f"   점수: {compression_score:.0f} ({'통과' if all_gates['compression']['passed'] else '실패'})")

        # ============ GATE 4: 포즈 세부 ============
        print("\n[GATE 4] 포즈 세부 체크...")
        pose_feedback = self._check_pose_details(curr_kpts, ref_kpts)
        all_gates['pose'] = {
            'feedback': pose_feedback
        }

        # 전체 점수 계산
        scores = [g['score'] for g in all_gates.values() if 'score' in g]
        overall_score = sum(scores) / len(scores) if scores else 0

        # 가장 큰 문제점 찾기
        failed_gates = [(name, gate) for name, gate in all_gates.items()
                       if 'passed' in gate and not gate['passed']]

        # 우선순위 순서
        priority_order = ['aspect_ratio', 'framing', 'composition', 'compression']
        critical_issue = None
        for gate_name in priority_order:
            if any(name == gate_name for name, _ in failed_gates):
                critical_issue = gate_name
                break

        return {
            'mode': 'FULL_ANALYSIS',
            'overall_score': overall_score,
            'all_gates': all_gates,
            'passed_gates': [name for name, gate in all_gates.items()
                           if 'passed' in gate and gate['passed']],
            'failed_gates': [name for name, _ in failed_gates],
            'critical_issue': critical_issue,
            'critical_feedback': all_gates[critical_issue]['feedback'] if critical_issue else None,
            'summary': self._generate_summary(all_gates),
            'friendly_summary': self._generate_friendly_summary(all_gates, overall_score)
        }

    def _production_mode(self, curr_kpts: Dict, ref_kpts: Dict,
                        curr_shape: Tuple, ref_shape: Tuple,
                        legacy_result: Any, device_type: str) -> Dict[str, Any]:
        """
        프로덕션 모드: 단계별 차단
        """
        print("\n[Production Mode] 단계별 Gate 점검")

        # ============ GATE 0: 종횡비 체크 (최우선) ============
        print("\n[GATE 0] 종횡비 체크...")
        aspect_score, aspect_feedback = self._check_aspect_ratio(curr_shape, ref_shape)

        if aspect_score < self.gate_thresholds['aspect_ratio']:
            print(f"   [X] 종횡비 불일치 (점수: {aspect_score})")
            return {
                'mode': 'PRODUCTION',
                'status': 'ASPECT_RATIO_MISMATCH',
                'gate_level': 0,
                'score': aspect_score,
                'overall_score': aspect_score,
                'critical_feedback': aspect_feedback,
                'message': '먼저 화면 비율을 맞추세요',
                'next_gates': ['framing', 'composition', 'compression']
            }

        print(f"   [OK] 종횡비 통과 (점수: {aspect_score})")

        # ============ GATE 1: 프레이밍 ============
        print("\n[GATE 1] 프레이밍 체크...")
        framing_score, framing_feedback = self._check_framing(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        if framing_score < self.gate_thresholds['framing']:
            print(f"   [X] 프레이밍 불일치 (점수: {framing_score})")
            return {
                'mode': 'PRODUCTION',
                'status': 'FRAMING_MISMATCH',
                'gate_level': 1,
                'score': framing_score,
                'overall_score': (aspect_score + framing_score) / 2,
                'gates_passed': ['aspect_ratio'],
                'critical_feedback': framing_feedback,
                'message': '화면에 담기는 범위를 조정하세요',
                'next_gates': ['composition', 'compression']
            }

        print(f"   [OK] 프레이밍 통과 (점수: {framing_score})")

        # ============ GATE 2: 구도 ============
        print("\n[GATE 2] 구도 체크...")
        composition_score, composition_feedback = self._check_composition(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        if composition_score < self.gate_thresholds['composition']:
            print(f"   [X] 구도 조정 필요 (점수: {composition_score})")
            return {
                'mode': 'PRODUCTION',
                'status': 'COMPOSITION_ADJUST',
                'gate_level': 2,
                'score': composition_score,
                'overall_score': (aspect_score + framing_score + composition_score) / 3,
                'gates_passed': ['aspect_ratio', 'framing'],
                'critical_feedback': composition_feedback,
                'message': '인물 위치를 조정하세요',
                'next_gates': ['compression', 'pose']
            }

        print(f"   [OK] 구도 통과 (점수: {composition_score})")

        # ============ GATE 3: 압축감 ============
        print("\n[GATE 3] 압축감 체크...")
        compression_score, compression_feedback = self._check_compression(
            legacy_result, device_type
        )

        if compression_score < self.gate_thresholds['compression']:
            print(f"   [X] 압축감 조정 필요 (점수: {compression_score})")
            return {
                'mode': 'PRODUCTION',
                'status': 'COMPRESSION_ADJUST',
                'gate_level': 3,
                'score': compression_score,
                'overall_score': (aspect_score + framing_score + composition_score + compression_score) / 4,
                'gates_passed': ['aspect_ratio', 'framing', 'composition'],
                'critical_feedback': compression_feedback,
                'message': '배경 압축감을 조정하세요',
                'next_gates': ['pose']
            }

        print(f"   [OK] 압축감 통과 (점수: {compression_score})")

        # ============ GATE 4: 포즈 세부 ============
        print("\n[GATE 4] 포즈 세부 체크...")
        pose_feedback = self._check_pose_details(curr_kpts, ref_kpts)

        final_score = (aspect_score + framing_score + composition_score + compression_score) / 4

        if pose_feedback:
            final_score = min(95, final_score + 5)  # 포즈 보너스

        return {
            'mode': 'PRODUCTION',
            'status': 'ALL_PASSED',
            'gate_level': 4,
            'score': final_score,
            'overall_score': final_score,
            'gates_passed': ['aspect_ratio', 'framing', 'composition', 'compression'],
            'optional_feedback': pose_feedback,
            'message': '기본기 완벽! 세부 포즈만 조정하면 됩니다',
            'next_gates': []
        }

    def _check_aspect_ratio(self, curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """
        Gate 0: 종횡비 체크
        """
        # 종횡비 계산
        curr_ratio = curr_shape[1] / curr_shape[0]  # width / height
        ref_ratio = ref_shape[1] / ref_shape[0]

        # 일반적인 종횡비 이름
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

        # 차이 계산
        diff = abs(curr_ratio - ref_ratio)

        # 허용 오차 (10%)
        tolerance = 0.1

        if diff < tolerance:
            return 100, None

        # 점수 계산 (차이가 클수록 점수 낮음)
        score = max(30, 100 - (diff * 100))

        # 조정 방법 - 명확한 변경 지시
        actions = []

        # 가장 중요한 메시지: 종횡비 변경 지시
        actions.append(f"종횡비를 {curr_name}에서 {ref_name}으로 변경하세요")

        # 구체적인 방법
        if curr_ratio > ref_ratio:
            # 현재가 더 가로로 넓음
            actions.append("방법 1: 세로로 크롭 (위아래 잘라내기)")
            actions.append("방법 2: 위아래에 검은 여백 추가")
        else:
            # 현재가 더 세로로 긴
            actions.append("방법 1: 가로로 크롭 (좌우 잘라내기)")
            actions.append("방법 2: 좌우에 검은 여백 추가")

        # 구체적인 크롭 가이드
        if curr_ratio != ref_ratio:
            if curr_ratio > ref_ratio:
                # 위아래 크롭 필요
                new_height = curr_shape[1] / ref_ratio
                crop_amount = curr_shape[0] - new_height
                actions.append(f"위아래 {crop_amount/2:.0f}px씩 크롭")
            else:
                # 좌우 크롭 필요
                new_width = curr_shape[0] * ref_ratio
                crop_amount = curr_shape[1] - new_width
                actions.append(f"좌우 {crop_amount/2:.0f}px씩 크롭")

        feedback = {
            'issue': 'ASPECT_RATIO_MISMATCH',
            'current_ratio': curr_ratio,
            'target_ratio': ref_ratio,
            'current_name': curr_name,
            'target_name': ref_name,
            'actions': actions
        }

        return score, feedback

    def _check_framing(self, curr_kpts: Dict, ref_kpts: Dict,
                      curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """Gate 1: 프레이밍 체크 (샷 타입 + 인물 비중 + 하단 여백)"""

        # 종합 프레이밍 분석 (새로운 분석기 사용)
        framing_result = self.framing_analyzer.analyze_framing_comprehensive(
            curr_kpts, ref_kpts, curr_shape, ref_shape
        )

        overall_score = framing_result['overall_score']
        feedback_data = framing_result['feedback']

        # Gate 통과 기준에 따른 피드백 생성
        if overall_score >= self.gate_thresholds['framing']:
            return overall_score, None

        # 피드백 생성
        feedback = {
            'issue': 'FRAMING_ADJUSTMENT_NEEDED',
            'shot_type': framing_result['shot_type'],
            'subject_ratio': framing_result['subject_ratio'],
            'bottom_space': framing_result['bottom_space'],
            'actions': feedback_data['actions'][:3],  # 상위 3개 액션만
            'summary': feedback_data['summary']
        }

        return overall_score, feedback

    def _check_composition(self, curr_kpts: Dict, ref_kpts: Dict,
                          curr_shape: Tuple, ref_shape: Tuple) -> Tuple[float, Optional[Dict]]:
        """Gate 2: 구도 체크 (인물 위치)"""

        curr_center = self._calculate_face_center(curr_kpts, curr_shape)
        ref_center = self._calculate_face_center(ref_kpts, ref_shape)

        if curr_center is None or ref_center is None:
            return 75, None

        curr_grid = self._to_grid_position(curr_center)
        ref_grid = self._to_grid_position(ref_center)

        if curr_grid == ref_grid:
            return 90, None

        movement = self._calculate_movement(curr_center, ref_center, curr_shape)

        distance = math.sqrt((curr_center[0] - ref_center[0])**2 +
                           (curr_center[1] - ref_center[1])**2)
        score = max(40, 80 - (distance * 100))

        feedback = {
            'issue': 'POSITION_MISMATCH',
            'current_grid': curr_grid,
            'target_grid': ref_grid,
            'actions': movement['actions'],
            'visual_guide': self._generate_grid_visual(curr_grid, ref_grid)
        }

        return score, feedback

    def _check_compression(self, legacy_result: Any, device_type: str) -> Tuple[float, Optional[Dict]]:
        """Gate 3: 압축감 체크"""

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

        diff = abs(ref_comp - curr_comp)

        if diff < 0.05:
            return 90, None

        zoom_adjustment = self._calculate_zoom_adjustment(curr_comp, ref_comp, device_type)

        score = max(50, 85 - (diff * 100))

        feedback = {
            'issue': 'COMPRESSION_MISMATCH',
            'current_compression': curr_comp,
            'target_compression': ref_comp,
            'actions': zoom_adjustment['actions']
        }

        return score, feedback

    def _check_pose_details(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[List[Dict]]:
        """Gate 4: 포즈 세부 사항"""

        minor_adjustments = []

        # 손 제스처 체크
        if len(ref_kpts['right_hand']) > 15 or len(ref_kpts['left_hand']) > 15:
            hand_feedback = self._check_hand_gestures(curr_kpts, ref_kpts)
            if hand_feedback:
                minor_adjustments.append(hand_feedback)

        # 얼굴 방향 체크
        if len(curr_kpts['face_landmarks']) > 30 and len(ref_kpts['face_landmarks']) > 30:
            face_feedback = self._check_face_direction(curr_kpts, ref_kpts)
            if face_feedback:
                minor_adjustments.append(face_feedback)

        # 어깨 정렬
        shoulder_feedback = self._check_shoulder_alignment(curr_kpts, ref_kpts)
        if shoulder_feedback:
            minor_adjustments.append(shoulder_feedback)

        return minor_adjustments if minor_adjustments else None

    def _generate_friendly_summary(self, all_gates: Dict, overall_score: float) -> str:
        """친절한 요약 메시지 생성 (현실적인 임계값)"""

        passed = []
        failed = []

        for gate_name, gate_data in all_gates.items():
            if 'passed' in gate_data:
                if gate_data['passed']:
                    passed.append(gate_name)
                else:
                    failed.append(gate_name)

        # 더 현실적인 임계값
        if overall_score >= 95:
            return "거의 완벽합니다! 레퍼런스와 매우 유사해요."
        elif overall_score >= 85:
            if len(failed) == 1:
                return f"레퍼런스와 비슷합니다. 미세 조정만 하면 더 좋아질 거예요."
            else:
                return "레퍼런스와 비슷하지만 약간의 조정이 필요합니다."
        elif overall_score >= 75:
            return "전반적으로 괜찮지만 몇 가지 개선이 필요합니다."
        elif overall_score >= 65:
            return "레퍼런스와 차이가 있으니 조정이 필요합니다."
        else:
            return "상당한 차이가 있어 단계적 조정이 필요해요."

    def _generate_summary(self, all_gates: Dict) -> str:
        """전체 분석 요약 생성"""

        summary = []

        # 종횡비
        if 'aspect_ratio' in all_gates:
            gate = all_gates['aspect_ratio']
            if gate['passed']:
                summary.append(f"[OK] 종횡비: {gate['score']:.0f}점")
            else:
                summary.append(f"[!] 종횡비 불일치: {gate['score']:.0f}점")

        # 프레이밍
        if 'framing' in all_gates:
            gate = all_gates['framing']
            if gate['passed']:
                summary.append(f"[OK] 프레이밍: {gate['score']:.0f}점")
            else:
                summary.append(f"[!] 프레이밍 조정 필요: {gate['score']:.0f}점")

        # 구도
        if 'composition' in all_gates:
            gate = all_gates['composition']
            if gate['passed']:
                summary.append(f"[OK] 구도: {gate['score']:.0f}점")
            else:
                summary.append(f"[!] 구도 조정 필요: {gate['score']:.0f}점")

        # 압축감
        if 'compression' in all_gates:
            gate = all_gates['compression']
            if gate['passed']:
                summary.append(f"[OK] 압축감: {gate['score']:.0f}점")
            else:
                summary.append(f"[!] 압축감 조정 필요: {gate['score']:.0f}점")

        return "\n".join(summary)

    # ================ Helper Functions (v4에서 가져옴) ================

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
        if len(kpts['foot_keypoints']) >= 4:
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
            distance = steps * 30
            zoom = 0.7 ** steps

            actions.append(f"카메라를 뒤로 {distance}cm 이동")
            actions.append(f"또는 줌을 {zoom:.1f}배로 축소")

            direction = 'wider'
        else:  # 더 좁게
            steps = curr_idx - ref_idx
            distance = steps * 30
            zoom = 1.4 ** steps

            actions.append(f"카메라를 앞으로 {distance}cm 이동")
            actions.append(f"또는 줌을 {zoom:.1f}배로 확대")

            direction = 'tighter'

        return {
            'actions': actions,
            'direction': direction,
            'steps': steps
        }

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

    def _calculate_movement(self, curr_pos: Tuple, ref_pos: Tuple,
                           img_shape: Tuple) -> Dict[str, Any]:
        """이동 거리 계산"""

        screen_width_cm = 15
        pixel_to_cm = screen_width_cm / img_shape[1]

        x_diff = (ref_pos[0] - curr_pos[0]) * img_shape[1] * pixel_to_cm
        y_diff = (ref_pos[1] - curr_pos[1]) * img_shape[0] * pixel_to_cm

        actions = []

        if abs(x_diff) > 1:
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
                    row += " * |"
                elif (x, y) == curr_grid:
                    row += " o |"
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
        return None  # 일단 생략

    def _check_shoulder_alignment(self, curr_kpts: Dict, ref_kpts: Dict) -> Optional[Dict]:
        """어깨 정렬 체크"""

        curr_body = curr_kpts.get('body_keypoints', {})
        ref_body = ref_kpts.get('body_keypoints', {})

        if not all(k in curr_body for k in ['left_shoulder', 'right_shoulder']):
            return None
        if not all(k in ref_body for k in ['left_shoulder', 'right_shoulder']):
            return None

        curr_left = curr_body['left_shoulder']['position']
        curr_right = curr_body['right_shoulder']['position']

        curr_tilt = math.degrees(math.atan2(
            curr_right[1] - curr_left[1],
            curr_right[0] - curr_left[0]
        ))

        if abs(curr_tilt) > 5:
            return {
                'category': 'posture',
                'importance': 'optional',
                'suggestion': f"어깨를 수평으로 맞춰주세요 (현재 {abs(curr_tilt):.1f}도 기울어짐)"
            }

        return None


def print_full_analysis(result: Dict, language: str = 'ko'):
    """Full Analysis 모드 결과 출력"""

    print("\n" + "="*70)
    print("[TryAngle v5] Full Analysis Report")
    print("="*70)

    # 전체 점수
    print(f"\n[전체 점수] {result.get('overall_score', 0):.0f}/100")

    # 요약
    if result.get('summary'):
        print(f"\n[요약]")
        print(result['summary'])

    # 모든 Gate 상태
    all_gates = result.get('all_gates', {})

    print(f"\n[Gate별 상세 분석]")
    print("-" * 60)

    # Gate 0: 종횡비
    if 'aspect_ratio' in all_gates:
        gate = all_gates['aspect_ratio']
        print(f"\nGate 0: 종횡비")
        print(f"  점수: {gate['score']:.0f}/100")
        print(f"  상태: {'통과' if gate['passed'] else '실패'}")
        if gate['feedback']:
            fb = gate['feedback']
            print(f"  현재: {fb['current_name']}")
            print(f"  목표: {fb['target_name']}")
            if fb['actions']:
                print(f"  조치: {fb['actions'][0]}")

    # Gate 1: 프레이밍
    if 'framing' in all_gates:
        gate = all_gates['framing']
        print(f"\nGate 1: 프레이밍")
        print(f"  점수: {gate['score']:.0f}/100")
        print(f"  상태: {'통과' if gate['passed'] else '실패'}")
        if gate['feedback']:
            fb = gate['feedback']
            print(f"  현재: {fb['current'].get('description', '')}")
            print(f"  목표: {fb['target'].get('description', '')}")
            if fb['actions']:
                print(f"  조치: {fb['actions'][0]}")

    # Gate 2: 구도
    if 'composition' in all_gates:
        gate = all_gates['composition']
        print(f"\nGate 2: 구도")
        print(f"  점수: {gate['score']:.0f}/100")
        print(f"  상태: {'통과' if gate['passed'] else '실패'}")
        if gate['feedback']:
            fb = gate['feedback']
            print(f"  현재 그리드: {fb.get('current_grid', '')}")
            print(f"  목표 그리드: {fb.get('target_grid', '')}")
            if fb.get('visual_guide'):
                print("\n[3분할 구도]")
                print(fb['visual_guide'])

    # Gate 3: 압축감
    if 'compression' in all_gates:
        gate = all_gates['compression']
        print(f"\nGate 3: 압축감")
        print(f"  점수: {gate['score']:.0f}/100")
        print(f"  상태: {'통과' if gate['passed'] else '실패'}")
        if gate['feedback']:
            fb = gate['feedback']
            print(f"  현재: {fb['current_compression']:.2f}")
            print(f"  목표: {fb['target_compression']:.2f}")
            if fb['actions']:
                print(f"  조치: {fb['actions'][0]}")

    # Gate 4: 포즈
    if 'pose' in all_gates:
        gate = all_gates['pose']
        if gate['feedback']:
            print(f"\nGate 4: 포즈 세부")
            for item in gate['feedback']:
                print(f"  - {item.get('suggestion', '')}")

    # 가장 중요한 문제
    if result.get('critical_issue'):
        print(f"\n[우선 해결 필요]")
        print(f"  -> {result['critical_issue']} 문제를 먼저 해결하세요!")

    print("\n" + "="*70)


def print_production_result(result: Dict, language: str = 'ko'):
    """Production 모드 결과 출력 (v4와 동일)"""

    print("\n" + "="*70)
    print("[TryAngle v5] Production Mode")
    print("="*70)

    print(f"\n[전체 점수] {result.get('overall_score', 0):.0f}/100")

    gate_level = result.get('gate_level', 0)
    status = result.get('status', 'UNKNOWN')

    print(f"\n[현재 상태] Gate {gate_level} - {status}")

    passed = result.get('gates_passed', [])
    if passed:
        print(f"\n[OK] 통과한 단계:")
        for gate in passed:
            gate_names = {
                'aspect_ratio': '종횡비',
                'framing': '프레이밍',
                'composition': '구도',
                'compression': '압축감'
            }
            print(f"   - {gate_names.get(gate, gate)}")

    if result.get('critical_feedback'):
        feedback = result['critical_feedback']
        print(f"\n[!] 우선 해결 필요:")
        print("-" * 60)

        if feedback.get('actions'):
            print(f"\n[즉시 실행]")
            for i, action in enumerate(feedback['actions'], 1):
                print(f"  {i}. {action}")

        if feedback.get('visual_guide'):
            print(f"\n[시각적 가이드]")
            print(feedback['visual_guide'])

    print("\n" + "="*70)


def main():
    """메인 실행 함수"""

    try:
        print("\n" + "="*70)
        print("  TryAngle v5 - Smart Feedback System  ")
        print("  (Full Analysis + Aspect Ratio Check)  ")
        print("="*70)

        # 언어 선택
        print("\n[Language / 언어]")
        print("  1. 한국어 (Korean)")
        print("  2. English")
        lang_choice = input("선택 (1-2, 기본=1): ").strip()

        language = 'ko' if lang_choice != '2' else 'en'

        # 모드 선택
        print("\n[분석 모드]")
        print("  1. Test Mode (모든 Gate 분석)")
        print("  2. Production Mode (단계별 차단)")
        mode_choice = input("선택 (1-2, 기본=1): ").strip()

        test_mode = mode_choice != '2'

        # 시스템 초기화
        feedback_system = SmartFeedbackV5(language=language)

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
            device_type=device_type,
            test_mode=test_mode
        )

        total_time = time.time() - start_time

        # 결과 출력
        if result.get('mode') == 'FULL_ANALYSIS':
            print_full_analysis(result, language)
        else:
            print_production_result(result, language)

        print(f"\n분석 시간: {total_time:.1f}초")

        # 재실행
        print("\n" + "="*70)
        again = input("\n다른 이미지를 비교하시겠습니까? (y/n): ").lower()
        if again == 'y':
            main()
        else:
            print("\nTryAngle v5를 이용해 주셔서 감사합니다!")

    except KeyboardInterrupt:
        print("\n\n종료합니다...")
    except Exception as e:
        print(f"\n오류: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()