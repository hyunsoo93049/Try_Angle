#!/usr/bin/env python3
"""
개선된 여백 분석 시스템
- 통합된 여백 분석 (상하/좌우 분리)
- 음수 백분율 처리
- 실용적인 피드백 생성
"""

import numpy as np
from typing import Dict, Tuple, List, Optional


class ImprovedMarginAnalyzer:
    """개선된 여백 분석기"""

    def __init__(self):
        """초기화"""
        # 여백 임계값 (더 현실적인 값)
        self.thresholds = {
            'horizontal': {
                'perfect': 0.05,    # 5% 이내 차이는 완벽
                'good': 0.10,       # 10% 이내는 양호
                'needs_adjustment': 0.15  # 15% 이상은 조정 필요
            },
            'vertical': {
                'perfect': 0.05,
                'good': 0.10,
                'needs_adjustment': 0.15
            }
        }

        # 피드백 우선순위
        self.priority_weights = {
            'horizontal_balance': 0.4,  # 좌우 균형 40%
            'vertical_balance': 0.3,    # 상하 균형 30%
            'bottom_space': 0.3         # 하단 여백 30%
        }

    def analyze_margins_unified(self, curr_kpts: Dict, ref_kpts: Dict,
                               curr_shape: Tuple, ref_shape: Tuple) -> Dict:
        """
        통합 여백 분석
        - 상하/좌우 분리 분석
        - 음수 처리
        - 실용적 피드백 생성
        """

        # 1. 바운딩 박스 계산
        curr_bbox = self._calculate_person_bbox(curr_kpts, curr_shape)
        ref_bbox = self._calculate_person_bbox(ref_kpts, ref_shape)

        # 2. 여백 계산 (음수 처리 포함)
        curr_margins = self._calculate_margins_safe(curr_bbox, curr_shape)
        ref_margins = self._calculate_margins_safe(ref_bbox, ref_shape)

        # 3. 상하/좌우 분석
        horizontal_analysis = self._analyze_horizontal_balance(curr_margins, ref_margins)
        vertical_analysis = self._analyze_vertical_balance(curr_margins, ref_margins)

        # 4. 하단 특별 분석 (테이블샷 등)
        bottom_special = self._analyze_bottom_special(curr_margins, ref_margins, curr_bbox, ref_bbox)

        # 5. 통합 점수 계산
        overall_score = self._calculate_overall_margin_score(
            horizontal_analysis, vertical_analysis, bottom_special
        )

        # 6. 실용적 피드백 생성
        actionable_feedback = self._generate_actionable_feedback(
            horizontal_analysis, vertical_analysis, bottom_special
        )

        return {
            'current_margins': curr_margins,
            'reference_margins': ref_margins,
            'horizontal': horizontal_analysis,
            'vertical': vertical_analysis,
            'bottom_special': bottom_special,
            'overall_score': overall_score,
            'actionable_feedback': actionable_feedback,
            'debug_info': {
                'current_bbox': curr_bbox,
                'reference_bbox': ref_bbox
            }
        }

    def _calculate_person_bbox(self, kpts: Dict, img_shape: Tuple) -> Dict:
        """
        인물 바운딩 박스 계산
        Returns: {'min_x', 'max_x', 'min_y', 'max_y'} in pixels
        """
        if kpts.get('num_persons', 0) == 0:
            # 인물 없음 - 중앙 가정
            return {
                'min_x': img_shape[1] * 0.25,
                'max_x': img_shape[1] * 0.75,
                'min_y': img_shape[0] * 0.25,
                'max_y': img_shape[0] * 0.75
            }

        all_points = []

        # 모든 키포인트 수집
        for body_part in kpts.get('body_keypoints', {}).values():
            if 'position' in body_part:
                all_points.append(body_part['position'])

        for face_point in kpts.get('face_landmarks', {}).values():
            if 'position' in face_point:
                all_points.append(face_point['position'])

        for foot_point in kpts.get('foot_keypoints', {}).values():
            if 'position' in foot_point:
                all_points.append(foot_point['position'])

        if not all_points:
            # 키포인트가 없으면 기본값
            return {
                'min_x': img_shape[1] * 0.25,
                'max_x': img_shape[1] * 0.75,
                'min_y': img_shape[0] * 0.25,
                'max_y': img_shape[0] * 0.75
            }

        points = np.array(all_points)
        return {
            'min_x': float(points[:, 0].min()),
            'max_x': float(points[:, 0].max()),
            'min_y': float(points[:, 1].min()),
            'max_y': float(points[:, 1].max())
        }

    def _calculate_margins_safe(self, bbox: Dict, img_shape: Tuple) -> Dict:
        """
        안전한 여백 계산 (음수 처리 포함)

        음수 의미:
        - 음수 = 인물이 프레임을 벗어남
        - 0 = 인물이 프레임 경계에 닿음
        - 양수 = 여백이 있음
        """
        img_height, img_width = img_shape[0], img_shape[1]

        margins = {
            'left': bbox['min_x'] / img_width,
            'right': (img_width - bbox['max_x']) / img_width,
            'top': bbox['min_y'] / img_height,
            'bottom': (img_height - bbox['max_y']) / img_height
        }

        # 프레임을 벗어난 경우 처리
        margins_safe = {}
        for key, value in margins.items():
            if value < -0.5:  # 50% 이상 벗어남
                margins_safe[key] = -0.5  # 최대 -50%로 제한
            elif value > 0.5:  # 50% 이상 여백
                margins_safe[key] = 0.5   # 최대 50%로 제한
            else:
                margins_safe[key] = value

            # 플래그 추가
            margins_safe[f'{key}_out_of_frame'] = value < 0

        return margins_safe

    def _analyze_horizontal_balance(self, curr: Dict, ref: Dict) -> Dict:
        """
        좌우 균형 분석
        """
        # 좌우 차이 계산
        curr_balance = curr['left'] - curr['right']  # 양수면 왼쪽 치우침
        ref_balance = ref['left'] - ref['right']

        # 중심 이동량 계산
        center_shift = curr_balance - ref_balance

        # 절대 여백 차이
        left_diff = abs(curr['left'] - ref['left'])
        right_diff = abs(curr['right'] - ref['right'])

        # 상태 판정
        if abs(center_shift) < self.thresholds['horizontal']['perfect']:
            status = 'perfect'
            score = 95
        elif abs(center_shift) < self.thresholds['horizontal']['good']:
            status = 'good'
            score = 85
        elif abs(center_shift) < self.thresholds['horizontal']['needs_adjustment']:
            status = 'needs_minor_adjustment'
            score = 70
        else:
            status = 'needs_adjustment'
            score = max(50, 85 - abs(center_shift) * 100)

        # 구체적 조정 방향
        adjustment = None
        if abs(center_shift) > self.thresholds['horizontal']['good']:
            percent = abs(center_shift) * 100
            if center_shift > 0:  # 현재가 더 왼쪽 치우침
                adjustment = {
                    'direction': 'right',
                    'percent': percent,
                    'camera_action': f"카메라를 오른쪽으로 {percent:.0f}% 이동",
                    'person_action': f"인물이 왼쪽으로 {self._to_steps(percent)} 이동"
                }
            else:  # 현재가 더 오른쪽 치우침
                adjustment = {
                    'direction': 'left',
                    'percent': percent,
                    'camera_action': f"카메라를 왼쪽으로 {percent:.0f}% 이동",
                    'person_action': f"인물이 오른쪽으로 {self._to_steps(percent)} 이동"
                }

        # 프레임 밖 처리
        out_of_frame_warning = None
        if curr.get('left_out_of_frame') or curr.get('right_out_of_frame'):
            if curr.get('left_out_of_frame') and curr.get('right_out_of_frame'):
                out_of_frame_warning = "인물이 좌우로 프레임을 벗어났습니다 (너무 가까움)"
            elif curr.get('left_out_of_frame'):
                out_of_frame_warning = "인물이 왼쪽 프레임을 벗어났습니다"
            else:
                out_of_frame_warning = "인물이 오른쪽 프레임을 벗어났습니다"

        return {
            'status': status,
            'score': score,
            'current_balance': curr_balance,
            'reference_balance': ref_balance,
            'center_shift': center_shift,
            'adjustment': adjustment,
            'out_of_frame_warning': out_of_frame_warning,
            'details': {
                'left_margin': {'current': curr['left'], 'reference': ref['left']},
                'right_margin': {'current': curr['right'], 'reference': ref['right']}
            }
        }

    def _analyze_vertical_balance(self, curr: Dict, ref: Dict) -> Dict:
        """
        상하 균형 분석 (개선: 인물의 절대 위치 고려)
        """
        # 인물의 절대 위치 계산 (0=최상단, 1=최하단)
        curr_total = curr['top'] + curr['bottom']
        ref_total = ref['top'] + ref['bottom']

        curr_position = curr['top'] / curr_total if curr_total > 0 else 0.5
        ref_position = ref['top'] / ref_total if ref_total > 0 else 0.5

        # 위치 차이 (양수 = 현재가 더 위쪽에 위치)
        position_diff = curr_position - ref_position

        # 상하 여백 차이도 함께 고려
        top_diff = curr['top'] - ref['top']
        bottom_diff = curr['bottom'] - ref['bottom']

        # 상태 판정
        if abs(position_diff) < 0.05:  # 5% 이내
            status = 'perfect'
            score = 95
        elif abs(position_diff) < 0.10:  # 10% 이내
            status = 'good'
            score = 85
        elif abs(position_diff) < 0.15:  # 15% 이내
            status = 'needs_minor_adjustment'
            score = 70
        else:
            status = 'needs_adjustment'
            score = max(50, 85 - abs(position_diff) * 100)

        # 구체적 조정 방향 (개선된 로직)
        adjustment = None
        if abs(position_diff) > 0.10:

            # 하이앵글 감지 (하단 여백이 상단보다 많으면)
            curr_is_high_angle = curr['bottom'] > curr['top']
            ref_is_high_angle = ref['bottom'] > ref['top']

            # 케이스 1: 현재가 더 위쪽에 위치 (하단 여백이 더 많음)
            if position_diff > 0:
                # 하이앵글인지 확인
                if curr_is_high_angle:
                    # 하이앵글 + 인물이 위쪽 = 카메라를 내리거나 틸트를 평행하게
                    angle = self._to_tilt_angle(abs(position_diff) * 100)
                    adjustment = {
                        'direction': 'lower_camera',
                        'position_diff': position_diff,
                        'is_high_angle': True,
                        'camera_action': f"카메라를 아래로 내리고, 앵글을 {angle}도 평행하게 조정",
                        'person_action': "인물이 프레임 아래쪽으로 이동"
                    }
                else:
                    # 평행 앵글 + 인물이 위쪽 = 카메라를 아래로 틸트
                    angle = self._to_tilt_angle(abs(position_diff) * 100)
                    adjustment = {
                        'direction': 'tilt_down',
                        'position_diff': position_diff,
                        'is_high_angle': False,
                        'camera_action': f"카메라를 {angle}도 아래로 틸트",
                        'person_action': "앉거나 자세를 낮추기"
                    }

            # 케이스 2: 현재가 더 아래쪽에 위치 (상단 여백이 더 많음)
            else:
                angle = self._to_tilt_angle(abs(position_diff) * 100)
                adjustment = {
                    'direction': 'tilt_up',
                    'position_diff': position_diff,
                    'is_high_angle': False,
                    'camera_action': f"카메라를 {angle}도 위로 틸트",
                    'person_action': "일어서거나 자세를 높이기"
                }

        # 프레임 밖 처리
        out_of_frame_warning = None
        if curr.get('top_out_of_frame') or curr.get('bottom_out_of_frame'):
            if curr.get('top_out_of_frame') and curr.get('bottom_out_of_frame'):
                out_of_frame_warning = "인물이 상하로 프레임을 벗어났습니다 (너무 가까움)"
            elif curr.get('top_out_of_frame'):
                out_of_frame_warning = "머리가 프레임을 벗어났습니다"
            else:
                out_of_frame_warning = "발이 프레임을 벗어났습니다"

        return {
            'status': status,
            'score': score,
            'current_position': curr_position,
            'reference_position': ref_position,
            'position_diff': position_diff,
            'adjustment': adjustment,
            'out_of_frame_warning': out_of_frame_warning,
            'details': {
                'top_margin': {'current': curr['top'], 'reference': ref['top']},
                'bottom_margin': {'current': curr['bottom'], 'reference': ref['bottom']},
                'current_is_high_angle': curr['bottom'] > curr['top'],
                'reference_is_high_angle': ref['bottom'] > ref['top']
            }
        }

    def _analyze_bottom_special(self, curr: Dict, ref: Dict,
                                curr_bbox: Dict, ref_bbox: Dict) -> Dict:
        """
        하단 특별 분석 (테이블샷, 카페샷 등)
        """
        # 하단 여백 비율
        curr_bottom = curr['bottom']
        ref_bottom = ref['bottom']

        # 테이블/하단 과다 판정
        table_heavy = curr_bottom < -0.1  # 하단이 10% 이상 잘림
        too_much_bottom = curr_bottom > ref_bottom + 0.15  # 15% 이상 많음
        too_little_bottom = curr_bottom < ref_bottom - 0.15  # 15% 이상 적음

        # 점수 계산
        diff = abs(curr_bottom - ref_bottom)
        if diff < 0.05:
            score = 95
            status = 'perfect'
        elif diff < 0.10:
            score = 85
            status = 'good'
        elif diff < 0.15:
            score = 75
            status = 'needs_minor_adjustment'
        else:
            score = max(60, 90 - diff * 100)
            status = 'needs_adjustment'

        # 특별 케이스 메시지
        special_message = None
        if table_heavy:
            special_message = "테이블/하단이 많이 잘렸습니다. 카메라를 위로 들거나 뒤로 물러나세요"
        elif too_much_bottom:
            special_message = "하단 여백이 너무 많습니다. 카메라를 아래로 내리거나 앞으로 이동하세요"
        elif too_little_bottom:
            special_message = "하단 여백이 부족합니다. 카메라를 위로 들거나 뒤로 물러나세요"

        return {
            'status': status,
            'score': score,
            'current_bottom': curr_bottom,
            'reference_bottom': ref_bottom,
            'table_heavy': table_heavy,
            'special_message': special_message
        }

    def _calculate_overall_margin_score(self, horizontal: Dict,
                                       vertical: Dict, bottom: Dict) -> float:
        """통합 점수 계산"""
        return (
            horizontal['score'] * self.priority_weights['horizontal_balance'] +
            vertical['score'] * self.priority_weights['vertical_balance'] +
            bottom['score'] * self.priority_weights['bottom_space']
        )

    def _generate_actionable_feedback(self, horizontal: Dict,
                                     vertical: Dict, bottom: Dict) -> Dict:
        """
        실용적이고 통합된 피드백 생성
        """
        # 우선순위 결정
        issues = []

        if horizontal['status'] == 'needs_adjustment':
            issues.append(('horizontal', horizontal['score']))
        if vertical['status'] == 'needs_adjustment':
            issues.append(('vertical', vertical['score']))
        if bottom['status'] == 'needs_adjustment':
            issues.append(('bottom', bottom['score']))

        # 점수 순으로 정렬 (낮은 것부터)
        issues.sort(key=lambda x: x[1])

        # 피드백 생성
        primary_action = None
        secondary_actions = []

        if not issues:
            return {
                'has_issues': False,
                'message': "여백이 레퍼런스와 잘 맞습니다!",
                'primary_action': None,
                'secondary_actions': []
            }

        # 주요 문제 해결
        main_issue = issues[0][0] if issues else None

        if main_issue == 'horizontal':
            if horizontal['adjustment']:
                primary_action = {
                    'type': 'horizontal_move',
                    'camera': horizontal['adjustment']['camera_action'],
                    'person': horizontal['adjustment']['person_action'],
                    'priority': 1
                }
        elif main_issue == 'vertical':
            if vertical['adjustment']:
                primary_action = {
                    'type': 'vertical_tilt',
                    'camera': vertical['adjustment']['camera_action'],
                    'person': vertical['adjustment']['person_action'],
                    'priority': 1
                }
        elif main_issue == 'bottom':
            if bottom['special_message']:
                primary_action = {
                    'type': 'bottom_adjustment',
                    'message': bottom['special_message'],
                    'priority': 1
                }

        # 보조 문제들
        for issue_type, score in issues[1:]:
            if issue_type == 'horizontal' and horizontal['adjustment']:
                secondary_actions.append({
                    'type': 'horizontal_move',
                    'message': f"추가로 {horizontal['adjustment']['camera_action']}",
                    'priority': 2
                })
            elif issue_type == 'vertical' and vertical['adjustment']:
                secondary_actions.append({
                    'type': 'vertical_tilt',
                    'message': f"추가로 {vertical['adjustment']['camera_action']}",
                    'priority': 2
                })

        # 통합 메시지 생성
        message_parts = []

        # 프레임 밖 경고
        if horizontal.get('out_of_frame_warning'):
            message_parts.append(horizontal['out_of_frame_warning'])
        if vertical.get('out_of_frame_warning'):
            message_parts.append(vertical['out_of_frame_warning'])

        # 주요 조정
        if primary_action:
            if primary_action['type'] == 'horizontal_move':
                message_parts.append(f"[좌우 조정] {primary_action['camera']} 또는 {primary_action['person']}")
            elif primary_action['type'] == 'vertical_tilt':
                message_parts.append(f"[상하 조정] {primary_action['camera']} 또는 {primary_action['person']}")
            elif primary_action['type'] == 'bottom_adjustment':
                message_parts.append(f"[하단 조정] {primary_action['message']}")

        return {
            'has_issues': True,
            'message': "\n".join(message_parts) if message_parts else "여백 조정이 필요합니다",
            'primary_action': primary_action,
            'secondary_actions': secondary_actions,
            'detailed_status': {
                'horizontal': horizontal['status'],
                'vertical': vertical['status'],
                'bottom': bottom['status']
            }
        }

    def _to_steps(self, percent: float) -> str:
        """퍼센트를 걸음수로 변환"""
        if percent < 5:
            return "아주 조금"
        elif percent < 10:
            return "반 걸음"
        elif percent < 20:
            return "한 걸음"
        elif percent < 30:
            return "두 걸음"
        elif percent < 40:
            return "세 걸음"
        else:
            return "네 걸음 이상"

    def _to_tilt_angle(self, percent: float) -> int:
        """퍼센트를 틸트 각도로 변환"""
        # 더 현실적인 각도
        if percent < 5:
            return 2
        elif percent < 10:
            return 5
        elif percent < 15:
            return 8
        elif percent < 20:
            return 10
        else:
            return min(15, int(percent * 0.5))


# 기존 framing_analyzer와 호환되는 인터페이스
def convert_to_legacy_format(unified_result: Dict) -> Dict:
    """
    통합 분석 결과를 기존 형식으로 변환
    (backward compatibility)
    """
    curr = unified_result['current_margins']
    ref = unified_result['reference_margins']

    # 기존 all_margins 형식
    legacy_format = {
        'current': {
            'top': max(0, curr['top']),  # 음수는 0으로
            'bottom': max(0, curr['bottom']),
            'left': max(0, curr['left']),
            'right': max(0, curr['right'])
        },
        'reference': {
            'top': max(0, ref['top']),
            'bottom': max(0, ref['bottom']),
            'left': max(0, ref['left']),
            'right': max(0, ref['right'])
        },
        'differences': {
            'top': abs(curr['top'] - ref['top']),
            'bottom': abs(curr['bottom'] - ref['bottom']),
            'left': abs(curr['left'] - ref['left']),
            'right': abs(curr['right'] - ref['right'])
        },
        'scores': {
            'top': 95 if abs(curr['top'] - ref['top']) < 0.05 else 75,
            'bottom': 95 if abs(curr['bottom'] - ref['bottom']) < 0.05 else 75,
            'left': 95 if abs(curr['left'] - ref['left']) < 0.05 else 75,
            'right': 95 if abs(curr['right'] - ref['right']) < 0.05 else 75
        },
        'overall_score': unified_result['overall_score'],
        'center_alignment': {
            'current': 0.5,  # 단순화
            'reference': 0.5,
            'difference': 0,
            'aligned': unified_result['horizontal']['status'] in ['perfect', 'good']
        }
    }

    return legacy_format