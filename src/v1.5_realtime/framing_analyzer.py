#!/usr/bin/env python3
"""
프레이밍 분석기 v2
샷 타입 + 여백 비중 + 인물 비중 종합 분석
"""

import numpy as np
from typing import Dict, Tuple, Optional, Any


class FramingAnalyzer:
    """프레이밍 종합 분석 (샷 타입 + 여백 + 인물 비중)"""

    def analyze_framing_comprehensive(self,
                                     curr_kpts: Dict,
                                     ref_kpts: Dict,
                                     curr_shape: Tuple,
                                     ref_shape: Tuple) -> Dict[str, Any]:
        """
        종합적인 프레이밍 분석

        Returns:
            {
                'shot_type': {...},
                'subject_ratio': {...},
                'bottom_space': {...},
                'all_margins': {...},
                'person_orientation': {...},
                'overall_score': float,
                'feedback': {...}
            }
        """

        # 0. 인물 방향 감지 (뒷모습/옆모습/정면)
        curr_orientation = self._detect_person_orientation(curr_kpts)
        ref_orientation = self._detect_person_orientation(ref_kpts)

        # 1. 샷 타입 분석 (방향 고려)
        shot_analysis = self._analyze_shot_type_improved(curr_kpts, ref_kpts,
                                                         curr_orientation, ref_orientation)

        # 2. 인물 비중 분석
        subject_analysis = self._analyze_subject_ratio(curr_kpts, ref_kpts,
                                                       curr_shape, ref_shape)

        # 3. 하단 여백(테이블) 분석
        bottom_analysis = self._analyze_bottom_space(curr_kpts, ref_kpts,
                                                     curr_shape, ref_shape)

        # 4. 4방향 여백 분석 (새로 추가)
        margins_analysis = self._analyze_all_margins(curr_kpts, ref_kpts,
                                                     curr_shape, ref_shape)

        # 5. 위치 움직임 분석 (⭐ 새로 추가)
        position_movements = self._analyze_position_movements(curr_kpts, ref_kpts,
                                                              curr_shape, ref_shape)

        # 6. 여백 조정 분석 (⭐ 새로 추가)
        margin_adjustments = self._margin_to_adjustments(margins_analysis)

        # 7. 종합 점수 계산 (가중치 적용)
        overall_score = self._calculate_overall_framing_score(
            shot_analysis, subject_analysis, bottom_analysis, margins_analysis
        )

        # 8. 통합 피드백 생성
        feedback = self._generate_comprehensive_feedback(
            shot_analysis, subject_analysis, bottom_analysis,
            margins_analysis, curr_orientation, ref_orientation
        )

        # 9. 액션 가능한 피드백 생성 (⭐ 새로 추가)
        actionable_feedback = self.generate_actionable_feedback(
            position_movements, margin_adjustments, overall_score
        )

        # 10. 종합 움직임 가이드 생성 (통합 버전)
        # 샷타입 조정 방법 계산
        shot_adjustment = None
        if shot_analysis['current']['type'] != shot_analysis['reference']['type']:
            shot_adjustment = self.generate_shot_type_adjustment(
                shot_analysis['current']['type'],
                shot_analysis['reference']['type']
            )

        # 얼굴 중심 계산 (압축감용 포지션)
        curr_center = self._calculate_face_center(curr_kpts, curr_shape)
        ref_center = self._calculate_face_center(ref_kpts, ref_shape)

        # 종합 움직임 가이드
        comprehensive_guide = self.generate_comprehensive_movement(
            curr_center, ref_center,
            margins_analysis.get('current'), margins_analysis.get('reference'),
            shot_diff=shot_adjustment,
            compression_diff=None  # 압축감은 별도 처리
        )

        return {
            'shot_type': shot_analysis,
            'subject_ratio': subject_analysis,
            'bottom_space': bottom_analysis,
            'all_margins': margins_analysis,
            'position_movements': position_movements,  # ⭐ NEW
            'margin_adjustments': margin_adjustments,  # ⭐ NEW
            'person_orientation': {
                'current': curr_orientation,
                'reference': ref_orientation
            },
            'overall_score': overall_score,
            'feedback': feedback,
            'actionable_feedback': actionable_feedback,  # ⭐ NEW
            'comprehensive_guide': comprehensive_guide  # ⭐ NEW
        }

    def _detect_person_orientation(self, kpts: Dict) -> Dict:
        """인물 방향 감지 (정면/뒷모습/옆모습)"""

        if kpts['num_persons'] == 0:
            return {'direction': 'no_person', 'confidence': 0}

        body = kpts.get('body_keypoints', {})
        face = kpts.get('face_landmarks', {})

        # 얼굴 특징점 개수로 판단
        face_count = len(face)

        # 어깨 체크
        has_both_shoulders = 'left_shoulder' in body and 'right_shoulder' in body
        has_one_shoulder = ('left_shoulder' in body) != ('right_shoulder' in body)

        # 코/얼굴 중심 체크
        has_nose = 'nose' in body and body['nose'].get('confidence', 0) > 0.3

        if face_count > 30 and has_nose:
            return {'direction': 'front', 'confidence': 0.9}
        elif face_count > 10:
            return {'direction': 'side', 'confidence': 0.7}
        elif has_both_shoulders and not has_nose:
            return {'direction': 'back', 'confidence': 0.8}
        elif has_one_shoulder:
            return {'direction': 'side', 'confidence': 0.6}
        else:
            # 키포인트가 너무 적어도 방향 추정
            if kpts.get('num_keypoints', 0) < 5:
                return {'direction': 'back_or_side', 'confidence': 0.3}
            return {'direction': 'unclear', 'confidence': 0.4}

    def _analyze_shot_type_improved(self, curr_kpts: Dict, ref_kpts: Dict,
                                   curr_orient: Dict = None, ref_orient: Dict = None) -> Dict:
        """
        개선된 샷 타입 분석
        - 키포인트 + 비율 기반 판단
        - 인물 방향 고려
        """

        curr_shot = self._determine_shot_with_ratio(curr_kpts, curr_orient)
        ref_shot = self._determine_shot_with_ratio(ref_kpts, ref_orient)

        # 같은 카테고리인지 체크
        # bust와 medium은 관대하게, knee와 full은 확실히 구분
        shot_categories = {
            'extreme_closeup': 'closeup_group',
            'closeup': 'closeup_group',
            'bust_shot': 'upper_body_group',  # bust와 medium만 같은 그룹
            'medium_shot': 'upper_body_group',
            'knee_shot': 'knee_only',  # 무릎샷은 별도 그룹
            'full_shot': 'full_only'    # 전신샷은 별도 그룹
        }

        curr_category = shot_categories.get(curr_shot['type'], 'unknown')
        ref_category = shot_categories.get(ref_shot['type'], 'unknown')

        if curr_shot['type'] == ref_shot['type']:
            score = 95  # 완전 일치
        elif curr_category == ref_category:
            score = 75  # 같은 카테고리 (bust vs medium만 해당)
        else:
            # 카테고리가 다르면 차이에 따라
            shot_order = ['extreme_closeup', 'closeup', 'bust_shot',
                         'medium_shot', 'knee_shot', 'full_shot']
            try:
                curr_idx = shot_order.index(curr_shot['type'])
                ref_idx = shot_order.index(ref_shot['type'])
                diff = abs(curr_idx - ref_idx)

                # knee와 full 간의 차이는 더 크게 감점
                if (curr_shot['type'] == 'knee_shot' and ref_shot['type'] == 'full_shot') or \
                   (curr_shot['type'] == 'full_shot' and ref_shot['type'] == 'knee_shot'):
                    score = 55  # knee와 full은 명확히 다름
                else:
                    score = max(50, 75 - (diff * 10))
            except:
                score = 60

        return {
            'current': curr_shot,
            'reference': ref_shot,
            'same_category': curr_category == ref_category,
            'score': score,
            'needs_adjustment': score < 80
        }

    def _determine_shot_with_ratio(self, kpts: Dict, orientation: Dict = None) -> Dict:
        """
        키포인트 + 화면 비율로 샷 타입 결정
        """

        # 샷 타입 한글 이름
        shot_names_kr = {
            'extreme_closeup': '익스트림 클로즈업',
            'closeup': '클로즈업',
            'bust_shot': '바스트샷',
            'medium_shot': '미디엄샷',
            'knee_shot': '무릎샷',
            'full_shot': '전신샷',
            'unknown': '알 수 없음'
        }

        if kpts['num_persons'] == 0:
            return {'type': 'no_person', 'name_kr': '인물 없음', 'confidence': 0}

        # 방향 정보가 있고 키포인트가 적을 때
        if orientation and orientation.get('direction') in ['back', 'side', 'back_or_side']:
            # 뒷모습/옆모습일 때는 더 관대한 기준 적용
            return self._determine_shot_for_partial_view(kpts, orientation)

        body = kpts.get('body_keypoints', {})
        face = kpts.get('face_landmarks', {})

        # 얼굴-어깨-팔꿈치-하단 비율 계산
        if 'nose' in body:
            nose_y = body['nose']['position'][1]

            # 가장 아래 보이는 키포인트 찾기
            lowest_y = nose_y
            lowest_part = 'face'

            check_parts = [
                ('shoulder', ['left_shoulder', 'right_shoulder']),
                ('elbow', ['left_elbow', 'right_elbow']),
                ('hip', ['left_hip', 'right_hip']),
                ('knee', ['left_knee', 'right_knee']),
                ('ankle', ['left_ankle', 'right_ankle'])
            ]

            for part_name, part_keys in check_parts:
                for key in part_keys:
                    if key in body:
                        y = body[key]['position'][1]
                        if y > lowest_y:
                            lowest_y = y
                            lowest_part = part_name

            # 비율 기반 판단
            if lowest_part == 'ankle' or len(kpts.get('foot_keypoints', {})) >= 3:
                return {'type': 'full_shot', 'name_kr': shot_names_kr['full_shot'], 'lowest': 'feet/ankle'}
            elif lowest_part == 'knee':
                return {'type': 'knee_shot', 'name_kr': shot_names_kr['knee_shot'], 'lowest': 'knee'}
            elif lowest_part == 'hip':
                # 힙이 보이지만 팔꿈치도 충분히 보이면 medium
                if 'left_elbow' in body or 'right_elbow' in body:
                    return {'type': 'medium_shot', 'name_kr': shot_names_kr['medium_shot'], 'lowest': 'hip+elbow'}
                else:
                    return {'type': 'bust_shot', 'name_kr': shot_names_kr['bust_shot'], 'lowest': 'hip'}
            elif lowest_part == 'elbow':
                return {'type': 'bust_shot', 'name_kr': shot_names_kr['bust_shot'], 'lowest': 'elbow'}
            elif lowest_part == 'shoulder':
                if len(face) > 50:
                    return {'type': 'closeup', 'name_kr': shot_names_kr['closeup'], 'lowest': 'shoulder+face'}
                else:
                    return {'type': 'bust_shot', 'name_kr': shot_names_kr['bust_shot'], 'lowest': 'shoulder'}
            else:
                return {'type': 'extreme_closeup', 'name_kr': shot_names_kr['extreme_closeup'], 'lowest': 'face_only'}

        return {'type': 'unknown', 'name_kr': shot_names_kr['unknown'], 'confidence': 0}

    def _determine_shot_for_partial_view(self, kpts: Dict, orientation: Dict) -> Dict:
        """뒷모습/옆모습일 때 샷 타입 판별"""

        shot_names_kr = {
            'closeup': '클로즈업',
            'bust_shot': '바스트샷',
            'medium_shot': '미디엄샷',
            'knee_shot': '무릎샷',
            'full_shot': '전신샷',
            'unclear': '불명확'
        }

        body = kpts.get('body_keypoints', {})
        direction = orientation.get('direction', 'unclear')

        # 어깨 기준으로 판단
        has_shoulders = 'left_shoulder' in body or 'right_shoulder' in body
        has_hips = 'left_hip' in body or 'right_hip' in body
        has_knees = 'left_knee' in body or 'right_knee' in body
        has_ankles = 'left_ankle' in body or 'right_ankle' in body

        # 방향 정보 포함
        dir_suffix = f" ({direction})"

        if has_ankles or len(kpts.get('foot_keypoints', {})) > 0:
            return {'type': 'full_shot', 'name_kr': shot_names_kr['full_shot'] + dir_suffix,
                   'confidence': 0.7, 'direction': direction}
        elif has_knees:
            return {'type': 'knee_shot', 'name_kr': shot_names_kr['knee_shot'] + dir_suffix,
                   'confidence': 0.7, 'direction': direction}
        elif has_hips:
            return {'type': 'medium_shot', 'name_kr': shot_names_kr['medium_shot'] + dir_suffix,
                   'confidence': 0.6, 'direction': direction}
        elif has_shoulders:
            return {'type': 'bust_shot', 'name_kr': shot_names_kr['bust_shot'] + dir_suffix,
                   'confidence': 0.5, 'direction': direction}
        else:
            return {'type': 'unclear', 'name_kr': shot_names_kr['unclear'] + dir_suffix,
                   'confidence': 0.3, 'direction': direction}

    def _analyze_subject_ratio(self, curr_kpts: Dict, ref_kpts: Dict,
                               curr_shape: Tuple, ref_shape: Tuple) -> Dict:
        """
        인물이 화면에서 차지하는 비중 분석
        """

        curr_ratio = self._calculate_subject_ratio(curr_kpts, curr_shape)
        ref_ratio = self._calculate_subject_ratio(ref_kpts, ref_shape)

        diff = abs(curr_ratio - ref_ratio)

        # 점수 계산
        if diff < 0.05:
            score = 95
        elif diff < 0.1:
            score = 85
        elif diff < 0.15:
            score = 75
        else:
            score = max(60, 90 - diff * 100)

        # 피드백 방향
        if curr_ratio < ref_ratio - 0.05:
            direction = "smaller"  # 인물이 더 작음
            action = "인물이 화면을 더 채우도록 가까이 가거나 줌인하세요"
        elif curr_ratio > ref_ratio + 0.05:
            direction = "larger"  # 인물이 더 큼
            action = "인물이 너무 크게 들어갑니다. 조금 멀어지거나 줌아웃하세요"
        else:
            direction = "similar"
            action = None

        return {
            'current_ratio': curr_ratio,
            'reference_ratio': ref_ratio,
            'difference': diff,
            'direction': direction,
            'score': score,
            'action': action
        }

    def _calculate_subject_ratio(self, kpts: Dict, img_shape: Tuple) -> float:
        """
        인물 바운딩 박스의 화면 비율 계산
        """

        if kpts['num_persons'] == 0:
            return 0.0

        # 모든 키포인트로 바운딩 박스 계산
        all_points = []

        for body_part in kpts.get('body_keypoints', {}).values():
            all_points.append(body_part['position'])

        for face_point in kpts.get('face_landmarks', {}).values():
            all_points.append(face_point['position'])

        if not all_points:
            return 0.0

        points = np.array(all_points)
        min_x, min_y = points.min(axis=0)
        max_x, max_y = points.max(axis=0)

        # 바운딩 박스 면적
        bbox_area = (max_x - min_x) * (max_y - min_y)

        # 전체 이미지 면적
        img_area = img_shape[0] * img_shape[1]

        return bbox_area / img_area if img_area > 0 else 0.0

    def _analyze_bottom_space(self, curr_kpts: Dict, ref_kpts: Dict,
                              curr_shape: Tuple, ref_shape: Tuple) -> Dict:
        """
        하단 여백(테이블 등) 비율 분석
        """

        curr_bottom = self._calculate_bottom_space_ratio(curr_kpts, curr_shape)
        ref_bottom = self._calculate_bottom_space_ratio(ref_kpts, ref_shape)

        diff = abs(curr_bottom - ref_bottom)

        # 점수 계산
        if diff < 0.05:
            score = 95
        elif diff < 0.1:
            score = 85
        elif diff < 0.15:
            score = 75
        else:
            score = max(60, 90 - diff * 100)

        # 피드백 방향
        if curr_bottom > ref_bottom + 0.1:
            direction = "too_much_bottom"
            action = "하단 여백(테이블)이 너무 많습니다. 카메라를 위로 올리거나 인물 중심으로 프레이밍하세요"
        elif curr_bottom < ref_bottom - 0.1:
            direction = "too_little_bottom"
            action = "하단 여백이 부족합니다. 테이블이나 배경을 조금 더 포함시켜보세요"
        else:
            direction = "similar"
            action = None

        return {
            'current_ratio': curr_bottom,
            'reference_ratio': ref_bottom,
            'difference': diff,
            'direction': direction,
            'score': score,
            'action': action,
            'table_heavy': curr_bottom > 0.3  # 테이블이 30% 이상이면 테이블 위주
        }

    def _calculate_bottom_space_ratio(self, kpts: Dict, img_shape: Tuple) -> float:
        """
        인물 아래 공간이 차지하는 비율 계산
        """

        if kpts['num_persons'] == 0:
            return 0.5  # 기본값

        # 인물의 최하단 Y 좌표 찾기
        lowest_y = 0

        for body_part in kpts.get('body_keypoints', {}).values():
            y = body_part['position'][1]
            if y > lowest_y:
                lowest_y = y

        # 하단 여백 비율 = (이미지 높이 - 인물 최하단) / 이미지 높이
        bottom_space = (img_shape[0] - lowest_y) / img_shape[0]

        return min(max(bottom_space, 0), 1)  # 0~1 범위로 클리핑

    def _analyze_all_margins(self, curr_kpts: Dict, ref_kpts: Dict,
                            curr_shape: Tuple, ref_shape: Tuple) -> Dict:
        """4방향 여백 분석 (상하좌우)"""

        curr_margins = self._calculate_four_margins(curr_kpts, curr_shape)
        ref_margins = self._calculate_four_margins(ref_kpts, ref_shape)

        # 각 방향별 차이 계산
        differences = {}
        scores = {}

        for direction in ['top', 'bottom', 'left', 'right']:
            diff = abs(curr_margins[direction] - ref_margins[direction])
            differences[direction] = diff

            # 점수 계산 (차이가 적을수록 높은 점수)
            if diff < 0.05:
                scores[direction] = 95
            elif diff < 0.1:
                scores[direction] = 85
            elif diff < 0.15:
                scores[direction] = 75
            else:
                scores[direction] = max(60, 90 - diff * 100)

        # 전체 여백 균형 점수
        overall_margin_score = sum(scores.values()) / 4

        # 중앙 정렬도 계산
        curr_center_x = (curr_margins['left'] - curr_margins['right']) / 2 + 0.5
        ref_center_x = (ref_margins['left'] - ref_margins['right']) / 2 + 0.5
        center_diff = abs(curr_center_x - ref_center_x)

        return {
            'current': curr_margins,
            'reference': ref_margins,
            'differences': differences,
            'scores': scores,
            'overall_score': overall_margin_score,
            'center_alignment': {
                'current': curr_center_x,
                'reference': ref_center_x,
                'difference': center_diff,
                'aligned': center_diff < 0.1
            }
        }

    def _calculate_four_margins(self, kpts: Dict, img_shape: Tuple) -> Dict:
        """인물 주변 4방향 여백 계산"""

        if kpts['num_persons'] == 0:
            return {'top': 0.5, 'bottom': 0.5, 'left': 0.5, 'right': 0.5}

        # 모든 키포인트로 바운딩 박스 계산
        all_points = []

        for body_part in kpts.get('body_keypoints', {}).values():
            if 'position' in body_part:
                all_points.append(body_part['position'])

        for face_point in kpts.get('face_landmarks', {}).values():
            if 'position' in face_point:
                all_points.append(face_point['position'])

        if not all_points:
            return {'top': 0.5, 'bottom': 0.5, 'left': 0.5, 'right': 0.5}

        points = np.array(all_points)
        min_x, min_y = points.min(axis=0)
        max_x, max_y = points.max(axis=0)

        # 이미지 크기
        img_width, img_height = img_shape[0], img_shape[1]

        # 각 방향 여백 비율 계산
        margins = {
            'top': min_y / img_height,
            'bottom': (img_height - max_y) / img_height,
            'left': min_x / img_width,
            'right': (img_width - max_x) / img_width
        }

        return margins

    def _calculate_overall_framing_score(self, shot: Dict, subject: Dict,
                                        bottom: Dict, margins: Dict = None) -> float:
        """
        프레이밍 종합 점수 계산
        """

        if margins:
            # 4방향 여백도 고려
            weights = {
                'shot_type': 0.25,      # 샷 타입 25%
                'subject_ratio': 0.35,  # 인물 비중 35%
                'bottom_space': 0.2,    # 하단 여백 20%
                'margins': 0.2          # 4방향 여백 균형 20%
            }

            weighted_score = (
                shot['score'] * weights['shot_type'] +
                subject['score'] * weights['subject_ratio'] +
                bottom['score'] * weights['bottom_space'] +
                margins['overall_score'] * weights['margins']
            )
        else:
            # 기존 방식
            weights = {
                'shot_type': 0.3,
                'subject_ratio': 0.4,
                'bottom_space': 0.3
            }

            weighted_score = (
                shot['score'] * weights['shot_type'] +
                subject['score'] * weights['subject_ratio'] +
                bottom['score'] * weights['bottom_space']
            )

        return weighted_score

    def _generate_comprehensive_feedback(self, shot: Dict, subject: Dict, bottom: Dict,
                                        margins: Dict = None, curr_orient: Dict = None,
                                        ref_orient: Dict = None) -> Dict:
        """
        통합 피드백 생성 (4방향 여백, 방향 정보 포함)
        """

        actions = []
        issues = []

        # 1. 샷 타입 피드백
        if shot['needs_adjustment']:
            if shot['same_category']:
                issues.append("minor_framing")
                actions.append("프레이밍이 레퍼런스와 거의 비슷하지만, 미세한 조정이 필요합니다")
            else:
                issues.append("shot_type_mismatch")
                curr_type = shot['current']['type']
                ref_type = shot['reference']['type']

                # knee와 full의 차이는 명확히 설명
                curr_name_kr = shot['current'].get('name_kr', curr_type)
                ref_name_kr = shot['reference'].get('name_kr', ref_type)

                if curr_type == 'knee_shot' and ref_type == 'full_shot':
                    actions.append(f"무릎샷에서 전신샷으로: 발까지 모두 나오도록 뒤로 물러나거나 줌아웃하세요")
                elif curr_type == 'full_shot' and ref_type == 'knee_shot':
                    actions.append(f"전신샷에서 무릎샷으로: 무릎까지만 나오도록 가까이 가거나 줌인하세요")
                else:
                    actions.append(f"샷 타입이 다릅니다 (현재: {curr_name_kr}, 목표: {ref_name_kr})")

        # 2. 인물 비중 피드백
        if subject['action']:
            issues.append("subject_ratio")
            actions.append(subject['action'])

            # 구체적인 수치 제공
            if subject['direction'] == "smaller":
                diff_percent = (subject['reference_ratio'] - subject['current_ratio']) * 100
                actions.append(f"인물 비중을 약 {diff_percent:.0f}% 더 늘려주세요")

        # 3. 하단 여백 피드백
        if bottom['action']:
            issues.append("bottom_space")
            actions.append(bottom['action'])

            if bottom['table_heavy']:
                actions.append("테이블/하단이 화면의 주요 부분을 차지하고 있어요. 인물 중심으로 조정해보세요")

        # 4방향 여백 이슈 추가
        if margins and margins.get('overall_score', 100) < 70:
            issues.append("margin_imbalance")

        # 종합 메시지 생성 (더 현실적인 임계값)
        issue_count = len(issues)
        if issue_count == 0:
            summary = "프레이밍이 레퍼런스와 거의 동일합니다!"
            severity = "excellent"
        elif issue_count == 1 and "minor_framing" in issues:
            summary = "전반적으로 비슷한 프레이밍이지만, 미세 조정이 필요합니다"
            severity = "minor"
        elif issue_count <= 2:
            summary = "몇 가지 조정이 필요하지만 전체적으로 유사합니다"
            severity = "moderate"
        else:
            summary = "프레이밍 조정이 필요합니다"
            severity = "major"

        return {
            'issues': issues,
            'actions': actions,
            'summary': summary,
            'severity': severity,
            'friendly_message': self._create_friendly_message(shot, subject, bottom)
        }

    def _create_friendly_message(self, shot: Dict, subject: Dict, bottom: Dict) -> str:
        """
        친절한 메시지 생성
        """

        messages = []

        # 샷 타입 평가
        if shot['current']['type'] == shot['reference']['type']:
            messages.append(f"샷 타입이 레퍼런스와 일치합니다 ({shot['current'].get('name_kr', shot['current']['type'])})")
        elif shot['same_category'] and shot['score'] >= 75:
            # bust와 medium 같은 경우
            messages.append(f"샷 타입은 유사합니다 ({shot['current'].get('name_kr', '')} / {shot['reference'].get('name_kr', '')})")
        elif not shot['same_category']:
            # 다른 카테고리인 경우
            messages.append(f"샷 타입이 다릅니다 ({shot['current'].get('name_kr', '')} vs {shot['reference'].get('name_kr', '')})")

        # 주요 문제점 제시
        main_issues = []

        if subject['direction'] == "smaller":
            main_issues.append("인물이 작게 나옴")
        elif subject['direction'] == "larger":
            main_issues.append("인물이 너무 크게 나옴")

        if bottom['table_heavy']:
            main_issues.append("테이블/하단이 많이 보임")
        elif bottom['direction'] == "too_little_bottom":
            main_issues.append("하단 여백 부족")

        if main_issues:
            messages.append(f"하지만 {', '.join(main_issues)} 문제가 있습니다")

        # 구체적 개선 방법
        if subject['direction'] == "smaller":
            messages.append("인물을 크게: 한 걸음 가까이 가거나 줌인하세요")
        elif subject['direction'] == "larger":
            messages.append("인물을 작게: 한 걸음 물러나거나 줌아웃하세요")

        if bottom['table_heavy']:
            messages.append("테이블 줄이기: 카메라를 위로 올려 상반신 중심으로 맞추세요")

        return " ".join(messages) if messages else "프레이밍이 레퍼런스와 잘 맞습니다!"

    def _analyze_position_movements(self, curr_kpts: Dict, ref_kpts: Dict,
                                   curr_shape: Tuple, ref_shape: Tuple) -> Dict:
        """위치 차이를 구체적 움직임으로 변환"""

        # 얼굴 중심 계산
        curr_center = self._calculate_face_center(curr_kpts, curr_shape)
        ref_center = self._calculate_face_center(ref_kpts, ref_shape)

        if not curr_center or not ref_center:
            return {'movements': [], 'grid_info': None}

        # 3x3 그리드 위치
        curr_grid = self._to_grid_position_korean(curr_center)
        ref_grid = self._to_grid_position_korean(ref_center)

        # 위치 차이 계산
        x_diff = ref_center[0] - curr_center[0]
        y_diff = ref_center[1] - curr_center[1]

        # 움직임 계산
        movements = []

        # 수평 이동 (좌우)
        if abs(x_diff) > 0.05:  # 5% 이상 차이
            percent = abs(x_diff) * 100
            steps = self._to_steps(percent)

            if x_diff > 0:  # 오른쪽으로 이동 필요
                movements.append({
                    'type': 'horizontal',
                    'direction': 'right',
                    'camera_action': f"카메라를 왼쪽으로 {percent:.0f}% 이동",
                    'subject_action': f"오른쪽으로 {steps} 이동",
                    'priority': 1 if percent > 20 else 2,
                    'percent': percent
                })
            else:  # 왼쪽으로 이동 필요
                movements.append({
                    'type': 'horizontal',
                    'direction': 'left',
                    'camera_action': f"카메라를 오른쪽으로 {percent:.0f}% 이동",
                    'subject_action': f"왼쪽으로 {steps} 이동",
                    'priority': 1 if percent > 20 else 2,
                    'percent': percent
                })

        # 수직 이동 (상하)
        if abs(y_diff) > 0.05:  # 5% 이상 차이
            percent = abs(y_diff) * 100
            angle = self._to_tilt_angle(percent)

            if y_diff > 0:  # 아래로 이동 필요
                movements.append({
                    'type': 'vertical',
                    'direction': 'down',
                    'camera_action': f"카메라를 {angle}도 아래로 틸트",
                    'subject_action': "앉거나 자세를 낮추기",
                    'priority': 2,
                    'percent': percent
                })
            else:  # 위로 이동 필요
                movements.append({
                    'type': 'vertical',
                    'direction': 'up',
                    'camera_action': f"카메라를 {angle}도 위로 틸트",
                    'subject_action': "일어서거나 자세를 높이기",
                    'priority': 2,
                    'percent': percent
                })

        return {
            'movements': movements,
            'grid_info': {
                'current': curr_grid,
                'target': ref_grid,
                'current_pos': curr_center,
                'target_pos': ref_center
            }
        }

    def _margin_to_adjustments(self, margin_data: Dict) -> list:
        """4방향 여백 차이를 구체적 조정으로 변환"""

        adjustments = []

        if not margin_data or 'differences' not in margin_data:
            return adjustments

        # 좌우 불균형 확인
        left_diff = margin_data['differences'].get('left', 0)
        right_diff = margin_data['differences'].get('right', 0)

        # 중앙 정렬 필요성 확인
        if left_diff > 0.1 or right_diff > 0.1:
            curr_left = margin_data['current']['left']
            ref_left = margin_data['reference']['left']

            if abs(curr_left - ref_left) > 0.1:
                percent = abs(curr_left - ref_left) * 100

                if curr_left > ref_left:  # 왼쪽 여백이 너무 많음
                    adjustments.append({
                        'type': 'centering',
                        'action': f"화면 중앙 맞추기: 오른쪽으로 {percent:.0f}% 이동",
                        'reason': "왼쪽 여백이 너무 많습니다",
                        'priority': 2
                    })
                else:  # 오른쪽 여백이 너무 많음
                    adjustments.append({
                        'type': 'centering',
                        'action': f"화면 중앙 맞추기: 왼쪽으로 {percent:.0f}% 이동",
                        'reason': "오른쪽 여백이 너무 많습니다",
                        'priority': 2
                    })

        # 상하 불균형 확인
        top_diff = margin_data['differences'].get('top', 0)
        bottom_diff = margin_data['differences'].get('bottom', 0)

        if top_diff > 0.1 or bottom_diff > 0.1:
            curr_top = margin_data['current']['top']
            ref_top = margin_data['reference']['top']

            if abs(curr_top - ref_top) > 0.1:
                angle = self._to_tilt_angle(abs(curr_top - ref_top) * 100)

                if curr_top > ref_top:  # 상단 여백이 너무 많음
                    adjustments.append({
                        'type': 'vertical_centering',
                        'action': f"카메라를 {angle}도 위로 틸트",
                        'reason': "상단 여백이 너무 많습니다",
                        'priority': 3
                    })
                else:  # 하단 여백이 너무 많음
                    adjustments.append({
                        'type': 'vertical_centering',
                        'action': f"카메라를 {angle}도 아래로 틸트",
                        'reason': "하단 여백이 너무 많습니다",
                        'priority': 3
                    })

        return adjustments

    def _calculate_face_center(self, kpts: Dict, img_shape: Tuple) -> Optional[Tuple[float, float]]:
        """얼굴 중심점 계산 (정규화된 좌표)"""

        if kpts.get('num_persons', 0) == 0:
            return None

        # 얼굴 랜드마크가 많으면 평균 사용
        face_landmarks = kpts.get('face_landmarks', {})

        if len(face_landmarks) > 30:
            # 모든 얼굴 포인트의 평균
            positions = [kpt['position'] for kpt in face_landmarks.values() if 'position' in kpt]
            if positions:
                import numpy as np
                avg_x = np.mean([p[0] for p in positions]) / img_shape[1]
                avg_y = np.mean([p[1] for p in positions]) / img_shape[0]
                return (avg_x, avg_y)

        # body keypoints에서 nose 찾기
        body_kpts = kpts.get('body_keypoints', {})
        if 'nose' in body_kpts:
            nose = body_kpts['nose']
            if nose.get('confidence', 0) > 0.3:
                return (nose['position'][0] / img_shape[1],
                       nose['position'][1] / img_shape[0])

        # 어깨 중심 사용 (fallback)
        if 'left_shoulder' in body_kpts and 'right_shoulder' in body_kpts:
            left = body_kpts['left_shoulder']
            right = body_kpts['right_shoulder']
            if left.get('confidence', 0) > 0.3 and right.get('confidence', 0) > 0.3:
                center_x = (left['position'][0] + right['position'][0]) / 2
                center_y = (left['position'][1] + right['position'][1]) / 2
                # 얼굴은 어깨보다 위에 있으므로 y를 조정
                center_y = center_y - img_shape[0] * 0.1  # 10% 위로
                return (center_x / img_shape[1], center_y / img_shape[0])

        return None

    def _to_grid_position_korean(self, center: Tuple[float, float]) -> Dict:
        """좌표를 한국어 3x3 그리드 위치로 변환"""

        # 그리드 좌표 계산
        grid_x = min(int(center[0] * 3) + 1, 3)
        grid_y = min(int(center[1] * 3) + 1, 3)

        # 한국어 그리드 이름
        grid_names = {
            (1, 1): "좌측 상단",
            (2, 1): "중앙 상단",
            (3, 1): "우측 상단",
            (1, 2): "좌측 중단",
            (2, 2): "정중앙",
            (3, 2): "우측 중단",
            (1, 3): "좌측 하단",
            (2, 3): "중앙 하단",
            (3, 3): "우측 하단"
        }

        return {
            'grid': (grid_x, grid_y),
            'name': grid_names.get((grid_x, grid_y), "알 수 없음"),
            'description': f"3분할 {grid_x}-{grid_y}구역"
        }

    def _to_steps(self, percent: float) -> str:
        """퍼센트를 걸음수로 변환"""
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

    def _to_tilt_angle(self, percent: float) -> int:
        """퍼센트를 틸트 각도로 변환"""
        # 5% = 3도, 10% = 5도, 15% = 8도, 20% = 10도
        return min(int(percent * 0.5), 15)

    def generate_actionable_feedback(self, position_movements: Dict,
                                    margin_adjustments: list,
                                    composition_score: float) -> Dict:
        """위치 기반 구체적 피드백 생성"""

        feedback_parts = []
        priority_actions = []

        # 구도 점수가 낮을 때 위치 피드백 우선
        if composition_score < 60 and position_movements.get('grid_info'):
            grid_info = position_movements['grid_info']

            # 현재와 목표 위치
            feedback_parts.append(f"[현재 위치] {grid_info['current']['name']} ({grid_info['current']['description']})")
            feedback_parts.append(f"[목표 위치] {grid_info['target']['name']} ({grid_info['target']['description']})")

            # 움직임 방법 추가
            movements = sorted(position_movements.get('movements', []),
                             key=lambda x: x['priority'])

            if movements:
                feedback_parts.append("\n[조정 방법]")
                for i, move in enumerate(movements[:2], 1):  # 최대 2개만
                    feedback_parts.append(f"  방법 {i}: {move['camera_action']}")
                    feedback_parts.append(f"  또는: {move['subject_action']}")
                    priority_actions.append(move)

        # 여백 조정이 필요한 경우
        elif margin_adjustments and composition_score < 80:
            adjustments = sorted(margin_adjustments, key=lambda x: x['priority'])

            if adjustments:
                feedback_parts.append("📐 여백 조정:")
                for adj in adjustments[:2]:  # 최대 2개만
                    feedback_parts.append(f"  • {adj['action']}")
                    if 'reason' in adj:
                        feedback_parts.append(f"    ({adj['reason']})")

        # 친근한 팁 추가
        if feedback_parts:
            feedback_parts.append("\n[팁] 레퍼런스와 같은 위치로 조정하면 구도가 훨씬 좋아집니다!")

        return {
            'message': "\n".join(feedback_parts) if feedback_parts else "프레이밍이 잘 맞습니다!",
            'priority_actions': priority_actions,
            'has_actionable': len(priority_actions) > 0
        }

    def generate_shot_type_adjustment(self, curr_type: str, ref_type: str) -> str:
        """샷타입 조정 방법 구체적 지시"""

        SHOT_TYPE_ORDER = ['extreme_closeup', 'closeup', 'bust_shot', 'medium_shot', 'knee_shot', 'full_shot']

        # 타입이 리스트에 없으면 기본값 반환
        if curr_type not in SHOT_TYPE_ORDER or ref_type not in SHOT_TYPE_ORDER:
            return "샷타입 조정 필요"

        curr_idx = SHOT_TYPE_ORDER.index(curr_type)
        ref_idx = SHOT_TYPE_ORDER.index(ref_type)

        if curr_idx < ref_idx:  # 더 넓게 찍어야 함
            steps = ref_idx - curr_idx
            if steps == 1:
                return "카메라를 조금 뒤로 빼거나 줌아웃 한 단계"
            else:
                return f"카메라를 뒤로 {steps}걸음 빼거나 줌아웃 {steps}단계"

        elif curr_idx > ref_idx:  # 더 가깝게
            steps = curr_idx - ref_idx
            if steps == 1:
                return "카메라를 조금 가까이 가거나 줌인 한 단계"
            else:
                return f"카메라를 앞으로 {steps}걸음 가거나 줌인 {steps}단계"

        return "샷타입이 같습니다"

    def generate_compression_adjustment(self, curr_comp: float, ref_comp: float) -> str:
        """압축감 조정 방법"""

        diff = ref_comp - curr_comp

        if abs(diff) < 0.05:
            return "압축감이 비슷합니다"

        if diff > 0:  # 압축감 더 필요
            if diff > 0.2:
                return "피사체에서 뒤로 많이 물러나고 줌인하세요 (압축감 증가)"
            else:
                return "피사체에서 한두 걸음 물러나고 줌인하세요 (압축감 증가)"
        else:  # 압축감 줄여야 함
            if abs(diff) > 0.2:
                return "피사체에 많이 가까이 가고 줌아웃하세요 (압축감 감소)"
            else:
                return "피사체에 한두 걸음 가까이 가고 줌아웃하세요 (압축감 감소)"

    def generate_comprehensive_movement(self, curr_center, ref_center, curr_margins, ref_margins,
                                       shot_diff=None, compression_diff=None) -> Dict:
        """구도, 여백, 샷타입, 압축감을 종합한 움직임 가이드"""

        movements = []

        # 1. 좌우 이동 (구도 + 좌우 여백)
        if curr_center and ref_center:
            x_diff = ref_center[0] - curr_center[0]

            if abs(x_diff) > 0.05:
                percent = abs(x_diff) * 100
                # 5% 단위로 반올림
                percent = round(percent / 5) * 5

                if x_diff > 0:
                    movements.append({
                        'step': 1,
                        'type': 'horizontal',
                        'instruction': f"카메라를 왼쪽으로 {percent}% 이동",
                        'alternative': f"인물이 오른쪽으로 {self._to_steps(percent)} 이동"
                    })
                else:
                    movements.append({
                        'step': 1,
                        'type': 'horizontal',
                        'instruction': f"카메라를 오른쪽으로 {percent}% 이동",
                        'alternative': f"인물이 왼쪽으로 {self._to_steps(percent)} 이동"
                    })

        # 2. 상하 틸트 (구도 + 상하 여백)
        if curr_center and ref_center:
            y_diff = ref_center[1] - curr_center[1]

            if abs(y_diff) > 0.05:
                # 틸트 각도 계산
                angle = self.calculate_tilt_angle(y_diff, curr_margins, ref_margins)

                if y_diff > 0:
                    movements.append({
                        'step': 2,
                        'type': 'tilt',
                        'instruction': f"카메라를 {angle}도 아래로 틸트",
                        'effect': "인물 상반신이 더 잘 보임"
                    })
                else:
                    movements.append({
                        'step': 2,
                        'type': 'tilt',
                        'instruction': f"카메라를 {angle}도 위로 틸트",
                        'effect': "배경이 더 많이 보임"
                    })

        # 3. 전후 이동 (샷타입 + 압축감)
        if shot_diff:
            movements.append({
                'step': 3,
                'type': 'distance',
                'instruction': shot_diff,
                'effect': "샷타입 조정"
            })

        if compression_diff and abs(compression_diff) > 0.1:
            movements.append({
                'step': 4,
                'type': 'compression',
                'instruction': self.generate_compression_adjustment(0, compression_diff),
                'effect': "압축감 조정"
            })

        return {
            'movements': movements,
            'total_steps': len(movements)
        }

    def calculate_tilt_angle(self, y_diff, curr_margins, ref_margins):
        """Y 차이와 여백을 고려한 틸트 각도 계산"""
        # 기본: y 차이의 30% 정도를 각도로
        base_angle = abs(y_diff) * 30

        # 여백 차이도 고려
        if curr_margins and ref_margins:
            top_diff = abs(curr_margins.get('top', 0) - ref_margins.get('top', 0))
            margin_angle = top_diff * 20
            # 둘 중 큰 값 사용
            final_angle = max(base_angle, margin_angle)
        else:
            final_angle = base_angle

        # 최대 15도, 반올림
        return min(15, round(final_angle))