#!/usr/bin/env python3
"""
RTMPose Wholebody Analyzer - 133개 키포인트 기반 정밀 포즈 분석
TryAngle v1.5 Phase 5 - Enhanced Version
"""

import sys
import os
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import math

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# RTMLib 임포트
try:
    from rtmlib import Wholebody, draw_skeleton
except ImportError:
    print("[ERROR] rtmlib 설치 필요: pip install rtmlib")
    sys.exit(1)


class RTMPoseWholebodyAnalyzer:
    """RTMPose Wholebody를 사용한 133개 키포인트 정밀 분석기"""

    # Wholebody 133 키포인트 구조
    # 0-16: Body (17개)
    # 17-22: Foot (6개)
    # 23-90: Face (68개)
    # 91-111: Left Hand (21개)
    # 112-132: Right Hand (21개)

    # COCO 17 Body Keypoints
    BODY_KEYPOINTS = {
        0: "nose",
        1: "left_eye", 2: "right_eye",
        3: "left_ear", 4: "right_ear",
        5: "left_shoulder", 6: "right_shoulder",
        7: "left_elbow", 8: "right_elbow",
        9: "left_wrist", 10: "right_wrist",
        11: "left_hip", 12: "right_hip",
        13: "left_knee", 14: "right_knee",
        15: "left_ankle", 16: "right_ankle"
    }

    # Foot Keypoints (17-22)
    FOOT_KEYPOINTS = {
        17: "left_big_toe",
        18: "left_small_toe",
        19: "left_heel",
        20: "right_big_toe",
        21: "right_small_toe",
        22: "right_heel"
    }

    # Face Landmarks (23-90) - 68 points
    FACE_KEYPOINTS = {
        # Jaw line (23-39)
        23: "jaw_1", 24: "jaw_2", 25: "jaw_3", 26: "jaw_4", 27: "jaw_5",
        28: "jaw_6", 29: "jaw_7", 30: "jaw_8", 31: "jaw_9",  # chin center
        32: "jaw_10", 33: "jaw_11", 34: "jaw_12", 35: "jaw_13",
        36: "jaw_14", 37: "jaw_15", 38: "jaw_16", 39: "jaw_17",

        # Right eyebrow (40-44)
        40: "right_eyebrow_1", 41: "right_eyebrow_2", 42: "right_eyebrow_3",
        43: "right_eyebrow_4", 44: "right_eyebrow_5",

        # Left eyebrow (45-49)
        45: "left_eyebrow_1", 46: "left_eyebrow_2", 47: "left_eyebrow_3",
        48: "left_eyebrow_4", 49: "left_eyebrow_5",

        # Nose (50-58)
        50: "nose_bridge_1", 51: "nose_bridge_2", 52: "nose_bridge_3", 53: "nose_bridge_4",
        54: "nose_tip", 55: "nose_bottom_1", 56: "nose_bottom_2", 57: "nose_bottom_3",
        58: "nose_bottom_4",

        # Right eye (59-64)
        59: "right_eye_1", 60: "right_eye_2", 61: "right_eye_3",
        62: "right_eye_4", 63: "right_eye_5", 64: "right_eye_6",

        # Left eye (65-70)
        65: "left_eye_1", 66: "left_eye_2", 67: "left_eye_3",
        68: "left_eye_4", 69: "left_eye_5", 70: "left_eye_6",

        # Outer lips (71-82)
        71: "lips_outer_1", 72: "lips_outer_2", 73: "lips_outer_3", 74: "lips_outer_4",
        75: "lips_outer_5", 76: "lips_outer_6", 77: "lips_outer_7", 78: "lips_outer_8",
        79: "lips_outer_9", 80: "lips_outer_10", 81: "lips_outer_11", 82: "lips_outer_12",

        # Inner lips (83-90)
        83: "lips_inner_1", 84: "lips_inner_2", 85: "lips_inner_3", 86: "lips_inner_4",
        87: "lips_inner_5", 88: "lips_inner_6", 89: "lips_inner_7", 90: "lips_inner_8"
    }

    # Hand Keypoints (각 손 21개)
    HAND_KEYPOINTS = {
        0: "wrist",
        # Thumb
        1: "thumb_cmc", 2: "thumb_mcp", 3: "thumb_ip", 4: "thumb_tip",
        # Index
        5: "index_mcp", 6: "index_pip", 7: "index_dip", 8: "index_tip",
        # Middle
        9: "middle_mcp", 10: "middle_pip", 11: "middle_dip", 12: "middle_tip",
        # Ring
        13: "ring_mcp", 14: "ring_pip", 15: "ring_dip", 16: "ring_tip",
        # Pinky
        17: "pinky_mcp", 18: "pinky_pip", 19: "pinky_dip", 20: "pinky_tip"
    }

    def __init__(self, mode='balanced', device='cpu'):
        """
        초기화

        Args:
            mode: 'lightweight', 'balanced', 'performance'
            device: 'cpu' or 'cuda'
        """
        print(f"[Wholebody Analyzer] 초기화 중... (mode: {mode}, device: {device})")

        try:
            # Wholebody 모델 초기화 (133 keypoints)
            self.wholebody = Wholebody(
                mode=mode,  # 모드 설정
                to_openpose=False,  # OpenPose 형식 변환 비활성화
                backend='onnxruntime',
                device=device
            )
            self.confidence_threshold = 0.5
            print("[Wholebody Analyzer] 초기화 완료 (133 키포인트)")
        except Exception as e:
            print(f"[Wholebody Analyzer] 초기화 실패: {e}")
            raise

    def extract_wholebody_keypoints(self, image: np.ndarray) -> Dict[str, Any]:
        """
        이미지에서 133개 키포인트 추출

        Args:
            image: RGB 이미지 배열

        Returns:
            {
                'keypoints': np.ndarray,  # (N, 133, 2) 좌표
                'scores': np.ndarray,      # (N, 133) 신뢰도
                'num_persons': int,        # 감지된 사람 수
                'body_keypoints': dict,    # 17개 바디 키포인트
                'face_landmarks': dict,    # 68개 얼굴 랜드마크
                'left_hand': dict,         # 21개 왼손 키포인트
                'right_hand': dict,        # 21개 오른손 키포인트
                'foot_keypoints': dict     # 6개 발 키포인트
            }
        """
        try:
            # Wholebody 추론 (133 keypoints)
            keypoints, scores = self.wholebody(image)

            # 결과 정리
            result = {
                'keypoints': keypoints,
                'scores': scores,
                'num_persons': 0,
                'body_keypoints': {},
                'face_landmarks': {},
                'left_hand': {},
                'right_hand': {},
                'foot_keypoints': {}
            }

            # 감지된 사람 수 확인
            if len(keypoints.shape) == 3:
                result['num_persons'] = keypoints.shape[0]
            elif len(keypoints.shape) == 2:
                result['num_persons'] = 1
                keypoints = keypoints.reshape(1, -1, 2)
                scores = scores.reshape(1, -1)

            # 첫 번째 사람 기준으로 키포인트 분류
            if result['num_persons'] > 0:
                person_kpts = keypoints[0]
                person_scores = scores[0]

                # Body (0-16)
                for i in range(17):
                    if person_scores[i] > self.confidence_threshold:
                        result['body_keypoints'][self.BODY_KEYPOINTS[i]] = {
                            'position': person_kpts[i],
                            'confidence': person_scores[i]
                        }

                # Foot (17-22)
                for i in range(17, 23):
                    if i < len(person_scores) and person_scores[i] > self.confidence_threshold:
                        result['foot_keypoints'][self.FOOT_KEYPOINTS[i]] = {
                            'position': person_kpts[i],
                            'confidence': person_scores[i]
                        }

                # Face (23-90)
                for i in range(23, 91):
                    if i < len(person_scores) and person_scores[i] > self.confidence_threshold:
                        result['face_landmarks'][self.FACE_KEYPOINTS[i]] = {
                            'position': person_kpts[i],
                            'confidence': person_scores[i]
                        }

                # Left Hand (91-111)
                for i in range(91, 112):
                    if i < len(person_scores) and person_scores[i] > self.confidence_threshold:
                        hand_idx = i - 91
                        result['left_hand'][self.HAND_KEYPOINTS[hand_idx]] = {
                            'position': person_kpts[i],
                            'confidence': person_scores[i]
                        }

                # Right Hand (112-132)
                for i in range(112, 133):
                    if i < len(person_scores) and person_scores[i] > self.confidence_threshold:
                        hand_idx = i - 112
                        result['right_hand'][self.HAND_KEYPOINTS[hand_idx]] = {
                            'position': person_kpts[i],
                            'confidence': person_scores[i]
                        }

            return result

        except Exception as e:
            print(f"[Wholebody Analyzer] 키포인트 추출 실패: {e}")
            return {
                'keypoints': np.array([]),
                'scores': np.array([]),
                'num_persons': 0,
                'body_keypoints': {},
                'face_landmarks': {},
                'left_hand': {},
                'right_hand': {},
                'foot_keypoints': {}
            }

    def analyze_face_direction(self, face_landmarks: Dict) -> Dict[str, Any]:
        """
        얼굴 랜드마크로 시선 방향 분석

        Args:
            face_landmarks: 68개 얼굴 랜드마크

        Returns:
            시선 방향, 얼굴 각도 등
        """
        if len(face_landmarks) < 10:
            return {'direction': 'unknown', 'confidence': 0}

        face_analysis = {}

        # 얼굴 중심선 계산 (코 다리와 턱 중심)
        if 'nose_bridge_1' in face_landmarks and 'jaw_9' in face_landmarks:
            nose_top = face_landmarks['nose_bridge_1']['position']
            chin = face_landmarks['jaw_9']['position']

            # 얼굴 수직 각도
            vertical_angle = math.degrees(math.atan2(
                chin[1] - nose_top[1],
                chin[0] - nose_top[0]
            )) - 90  # 수직 기준으로 변환

            face_analysis['vertical_tilt'] = {
                'angle': vertical_angle,
                'description': self._describe_vertical_tilt(vertical_angle)
            }

        # 얼굴 좌우 회전 (눈 위치 비교)
        if 'left_eye_3' in face_landmarks and 'right_eye_3' in face_landmarks:
            left_eye = face_landmarks['left_eye_3']['position']
            right_eye = face_landmarks['right_eye_3']['position']

            # 눈 간격으로 얼굴 회전 추정
            eye_distance = np.linalg.norm(left_eye - right_eye)

            # 코와 눈 중심의 상대 위치
            if 'nose_tip' in face_landmarks:
                nose = face_landmarks['nose_tip']['position']
                eye_center = (left_eye + right_eye) / 2
                nose_offset = nose[0] - eye_center[0]

                # 얼굴 회전 추정 (좌우)
                rotation = nose_offset / (eye_distance + 1e-6) * 100

                face_analysis['horizontal_rotation'] = {
                    'offset_ratio': rotation,
                    'direction': self._get_face_direction(rotation)
                }

        # 표정 분석 (입 모양)
        if self._has_mouth_landmarks(face_landmarks):
            mouth_analysis = self._analyze_mouth_expression(face_landmarks)
            face_analysis['expression'] = mouth_analysis

        # 시선 추정 (눈동자 위치는 없지만 눈 형태로 추정)
        if self._has_eye_landmarks(face_landmarks):
            eye_analysis = self._analyze_eye_gaze(face_landmarks)
            face_analysis['gaze'] = eye_analysis

        return face_analysis

    def analyze_hand_gesture(self, hand_keypoints: Dict, hand_type: str = 'left') -> Dict[str, Any]:
        """
        손 제스처 분석

        Args:
            hand_keypoints: 21개 손 키포인트
            hand_type: 'left' or 'right'

        Returns:
            손 제스처, 손가락 상태 등
        """
        if len(hand_keypoints) < 5:
            return {'gesture': 'unknown', 'confidence': 0}

        hand_analysis = {
            'hand_type': hand_type,
            'fingers': {}
        }

        # 각 손가락 상태 분석
        finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']

        for finger in finger_names:
            finger_status = self._analyze_finger_status(hand_keypoints, finger)
            if finger_status:
                hand_analysis['fingers'][finger] = finger_status

        # 전체 손 제스처 추정
        gesture = self._estimate_hand_gesture(hand_analysis['fingers'])
        hand_analysis['gesture'] = gesture

        # 손의 방향 (손목 기준)
        if 'wrist' in hand_keypoints:
            wrist_pos = hand_keypoints['wrist']['position']
            hand_analysis['wrist_position'] = {
                'x': wrist_pos[0],
                'y': wrist_pos[1]
            }

        return hand_analysis

    def get_enhanced_shot_type(self, wholebody_data: Dict, img_height: int) -> Dict[str, Any]:
        """
        133개 키포인트 기반 정밀 샷 타입 판단

        Args:
            wholebody_data: extract_wholebody_keypoints의 결과
            img_height: 이미지 높이

        Returns:
            향상된 샷 타입 정보
        """
        if wholebody_data['num_persons'] == 0:
            return {'type': 'unknown', 'coverage': 0, 'confidence': 0}

        body = wholebody_data['body_keypoints']
        face = wholebody_data['face_landmarks']
        foot = wholebody_data['foot_keypoints']

        # 얼굴 세부 정보 확인
        has_detailed_face = len(face) > 30  # 30개 이상 얼굴 랜드마크
        has_eyes = 'left_eye_3' in face and 'right_eye_3' in face
        has_mouth = 'lips_outer_5' in face  # 상단 입술 중앙

        # 발 세부 정보
        has_toes = 'left_big_toe' in foot or 'right_big_toe' in foot

        # 키포인트 범위 계산
        all_keypoints = wholebody_data['keypoints'][0]
        all_scores = wholebody_data['scores'][0]

        visible_y_coords = []
        for i in range(len(all_scores)):
            if all_scores[i] > self.confidence_threshold:
                visible_y_coords.append(all_keypoints[i][1])

        if not visible_y_coords:
            return {'type': 'unknown', 'coverage': 0, 'confidence': 0}

        top_y = min(visible_y_coords)
        bottom_y = max(visible_y_coords)
        coverage = (bottom_y - top_y) / img_height

        # 정밀한 샷 타입 결정
        shot_type = {}

        # 우선순위: 발 -> 무릎 -> 엉덩이 -> 어깨 -> 얼굴
        # (넓은 범위부터 체크)

        # 전신샷: 발가락 키포인트가 있으면 우선 전신샷
        if has_toes:
            shot_type = {
                'name': 'full_shot',
                'desc': '전신샷',
                'parts': '머리부터 발끝까지',
                'hint': '전체 포즈와 스탠스가 보임',
                'foot_detail': has_toes
            }

        # 무릎샷 (무릎까지)
        elif ('left_knee' in body or 'right_knee' in body):
            shot_type = {
                'name': 'knee_shot',
                'desc': '무릎샷 (3/4샷)',
                'parts': '머리부터 무릎까지',
                'hint': '대부분의 신체가 보임'
            }

        # 미디엄샷 (허리/엉덩이까지)
        elif 'left_hip' in body and 'right_hip' in body:
            shot_type = {
                'name': 'medium_shot',
                'desc': '미디엄샷',
                'parts': '머리부터 허리까지',
                'hint': '상반신과 손 제스처가 보임',
                'hand_gesture_clear': len(wholebody_data['left_hand']) > 15 or len(wholebody_data['right_hand']) > 15
            }

        # 바스트샷 (가슴까지)
        elif 'left_shoulder' in body and 'right_shoulder' in body:
            shot_type = {
                'name': 'bust_shot',
                'desc': '바스트샷',
                'parts': '머리부터 가슴까지',
                'hint': '상체 제스처와 표정이 보임',
                'hand_visibility': len(wholebody_data['left_hand']) > 10 or len(wholebody_data['right_hand']) > 10
            }

        # 클로즈업 (얼굴과 어깨)
        elif has_detailed_face and len(face) > 30:
            shot_type = {
                'name': 'closeup',
                'desc': '클로즈업',
                'parts': '얼굴과 어깨',
                'hint': '표정이 선명하게 보임',
                'face_detail_level': 'high'
            }

        # 익스트림 클로즈업 (얼굴만)
        elif has_detailed_face and len(face) > 50:
            shot_type = {
                'name': 'extreme_closeup',
                'desc': '익스트림 클로즈업',
                'parts': '얼굴 세부',
                'hint': '얼굴 표정과 감정이 매우 선명함',
                'face_detail_level': 'very_high'
            }

        else:
            shot_type = {
                'name': 'custom',
                'desc': '비표준 구도',
                'parts': '커스텀',
                'hint': f'화면 대비 {coverage*100:.0f}% 차지'
            }

        # 신뢰도 계산 (전체 133개 중 유효 키포인트 비율)
        confidence = np.sum(all_scores > self.confidence_threshold) / 133

        return {
            'type': shot_type['name'],
            'description': shot_type['desc'],
            'coverage': coverage,
            'confidence': confidence,
            'visible_parts': shot_type['parts'],
            'adjustment_hint': shot_type['hint'],
            'face_landmarks_count': len(face),
            'hand_keypoints_count': len(wholebody_data['left_hand']) + len(wholebody_data['right_hand']),
            'details': shot_type
        }

    def analyze_body_posture(self, wholebody_data: Dict) -> Dict[str, Any]:
        """
        전신 자세 분석 (어깨, 척추, 골반 정렬 등)

        Args:
            wholebody_data: 133개 키포인트 데이터

        Returns:
            자세 분석 결과
        """
        body = wholebody_data['body_keypoints']
        posture = {}

        # 어깨 정렬
        if 'left_shoulder' in body and 'right_shoulder' in body:
            left_sh = body['left_shoulder']['position']
            right_sh = body['right_shoulder']['position']

            shoulder_tilt = math.degrees(math.atan2(
                right_sh[1] - left_sh[1],
                right_sh[0] - left_sh[0]
            ))

            posture['shoulder_alignment'] = {
                'angle': shoulder_tilt,
                'status': self._evaluate_shoulder_alignment(shoulder_tilt),
                'adjustment': self._get_shoulder_correction(shoulder_tilt)
            }

        # 골반 정렬
        if 'left_hip' in body and 'right_hip' in body:
            left_hip = body['left_hip']['position']
            right_hip = body['right_hip']['position']

            hip_tilt = math.degrees(math.atan2(
                right_hip[1] - left_hip[1],
                right_hip[0] - left_hip[0]
            ))

            posture['hip_alignment'] = {
                'angle': hip_tilt,
                'status': self._evaluate_hip_alignment(hip_tilt),
                'balance': abs(hip_tilt) < 5
            }

        # 척추 곡선 (간접 추정)
        if all(k in body for k in ['nose', 'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip']):
            spine_curve = self._estimate_spine_curve(body)
            posture['spine'] = spine_curve

        # 무게 중심
        if len(body) >= 10:
            center_of_mass = self._calculate_center_of_mass(body)
            posture['center_of_mass'] = center_of_mass

        # 발 스탠스
        if 'left_ankle' in body and 'right_ankle' in body:
            stance = self._analyze_stance(body, wholebody_data['foot_keypoints'])
            posture['stance'] = stance

        return posture

    def _describe_vertical_tilt(self, angle: float) -> str:
        """얼굴 수직 각도 설명"""
        if abs(angle) < 5:
            return "정면"
        elif angle > 0:
            return f"위를 {abs(angle):.1f}도 바라봄"
        else:
            return f"아래를 {abs(angle):.1f}도 바라봄"

    def _get_face_direction(self, rotation: float) -> str:
        """얼굴 좌우 방향"""
        if abs(rotation) < 10:
            return "정면"
        elif rotation > 0:
            return f"왼쪽으로 {abs(rotation):.0f}% 회전"
        else:
            return f"오른쪽으로 {abs(rotation):.0f}% 회전"

    def _has_mouth_landmarks(self, face: Dict) -> bool:
        """입 랜드마크 존재 여부"""
        mouth_keys = ['lips_outer_1', 'lips_outer_5', 'lips_outer_7']
        return any(k in face for k in mouth_keys)

    def _analyze_mouth_expression(self, face: Dict) -> Dict:
        """입 표정 분석"""
        # 입 꼬리 위치로 표정 추정
        if 'lips_outer_1' in face and 'lips_outer_7' in face:
            left_corner = face['lips_outer_1']['position']
            right_corner = face['lips_outer_7']['position']

            # 입 중앙선 대비 입꼬리 높이
            if 'lips_outer_4' in face:  # 하단 입술 중앙
                bottom_center = face['lips_outer_4']['position']
                avg_corner_height = (left_corner[1] + right_corner[1]) / 2

                if avg_corner_height < bottom_center[1] - 5:
                    return {'type': 'smile', 'confidence': 0.7}
                elif avg_corner_height > bottom_center[1] + 5:
                    return {'type': 'frown', 'confidence': 0.7}

        return {'type': 'neutral', 'confidence': 0.5}

    def _has_eye_landmarks(self, face: Dict) -> bool:
        """눈 랜드마크 존재 여부"""
        return 'left_eye_3' in face and 'right_eye_3' in face

    def _analyze_eye_gaze(self, face: Dict) -> Dict:
        """시선 방향 추정"""
        # 눈 형태로 대략적인 시선 추정
        if 'left_eye_1' in face and 'left_eye_4' in face:
            left_eye_width = abs(face['left_eye_4']['position'][0] - face['left_eye_1']['position'][0])

            if 'right_eye_1' in face and 'right_eye_4' in face:
                right_eye_width = abs(face['right_eye_4']['position'][0] - face['right_eye_1']['position'][0])

                # 양쪽 눈 너비 비교로 시선 방향 추정
                width_ratio = left_eye_width / (right_eye_width + 1e-6)

                if width_ratio > 1.2:
                    return {'direction': 'looking_right', 'confidence': 0.6}
                elif width_ratio < 0.8:
                    return {'direction': 'looking_left', 'confidence': 0.6}

        return {'direction': 'looking_forward', 'confidence': 0.5}

    def _analyze_finger_status(self, hand: Dict, finger: str) -> Optional[Dict]:
        """개별 손가락 상태 분석"""
        finger_keys = {
            'thumb': ['thumb_cmc', 'thumb_mcp', 'thumb_ip', 'thumb_tip'],
            'index': ['index_mcp', 'index_pip', 'index_dip', 'index_tip'],
            'middle': ['middle_mcp', 'middle_pip', 'middle_dip', 'middle_tip'],
            'ring': ['ring_mcp', 'ring_pip', 'ring_dip', 'ring_tip'],
            'pinky': ['pinky_mcp', 'pinky_pip', 'pinky_dip', 'pinky_tip']
        }

        if finger not in finger_keys:
            return None

        keys = finger_keys[finger]
        if all(k in hand for k in keys):
            # 손가락 굽힘 정도 계산
            joints = [hand[k]['position'] for k in keys]

            # 관절 각도로 굽힘 판단
            is_extended = self._is_finger_extended(joints)

            return {
                'status': 'extended' if is_extended else 'bent',
                'confidence': 0.7
            }

        return None

    def _is_finger_extended(self, joints: List[np.ndarray]) -> bool:
        """손가락이 펴져있는지 판단"""
        if len(joints) < 3:
            return False

        # 첫 관절과 끝 관절의 직선 거리
        direct_dist = np.linalg.norm(joints[-1] - joints[0])

        # 각 관절 간 거리의 합
        total_dist = sum(np.linalg.norm(joints[i+1] - joints[i]) for i in range(len(joints)-1))

        # 직선 거리와 총 거리의 비율로 판단
        return (direct_dist / (total_dist + 1e-6)) > 0.8

    def _estimate_hand_gesture(self, fingers: Dict) -> str:
        """손 제스처 추정"""
        extended_count = sum(1 for f in fingers.values() if f and f['status'] == 'extended')

        if extended_count == 0:
            return "fist"
        elif extended_count == 1:
            if fingers.get('index', {}).get('status') == 'extended':
                return "pointing"
            elif fingers.get('thumb', {}).get('status') == 'extended':
                return "thumbs_up"
        elif extended_count == 2:
            if fingers.get('index', {}).get('status') == 'extended' and \
               fingers.get('middle', {}).get('status') == 'extended':
                return "peace"
        elif extended_count == 5:
            return "open_palm"

        return f"{extended_count}_fingers"

    def _evaluate_shoulder_alignment(self, angle: float) -> str:
        """어깨 정렬 평가"""
        if abs(angle) < 2:
            return "완벽한 수평"
        elif abs(angle) < 5:
            return "양호한 정렬"
        elif abs(angle) < 10:
            return "약간 기울어짐"
        else:
            return "심하게 기울어짐"

    def _get_shoulder_correction(self, angle: float) -> str:
        """어깨 교정 방법"""
        if abs(angle) < 2:
            return "현재 자세 유지"
        elif angle > 0:
            return f"오른쪽 어깨를 {abs(angle):.1f}도 낮추기"
        else:
            return f"왼쪽 어깨를 {abs(angle):.1f}도 낮추기"

    def _evaluate_hip_alignment(self, angle: float) -> str:
        """골반 정렬 평가"""
        if abs(angle) < 3:
            return "균형잡힘"
        elif abs(angle) < 7:
            return "약간 기울어짐"
        else:
            return "불균형"

    def _estimate_spine_curve(self, body: Dict) -> Dict:
        """척추 곡선 추정"""
        # 간단한 추정: 머리-어깨-골반 정렬
        nose = body['nose']['position']
        shoulder_center = (body['left_shoulder']['position'] + body['right_shoulder']['position']) / 2
        hip_center = (body['left_hip']['position'] + body['right_hip']['position']) / 2

        # 정렬 각도
        alignment_angle = math.degrees(math.atan2(
            hip_center[0] - nose[0],
            hip_center[1] - nose[1]
        ))

        return {
            'alignment': alignment_angle,
            'status': "정렬됨" if abs(alignment_angle) < 5 else "기울어짐"
        }

    def _calculate_center_of_mass(self, body: Dict) -> Dict:
        """무게 중심 계산"""
        positions = [kpt['position'] for kpt in body.values()]
        center = np.mean(positions, axis=0)

        return {
            'x': center[0],
            'y': center[1],
            'balance': "중앙" if abs(center[0] - 360) < 50 else "편향"  # 720px 기준
        }

    def _analyze_stance(self, body: Dict, foot: Dict) -> Dict:
        """발 스탠스 분석"""
        left_ankle = body['left_ankle']['position']
        right_ankle = body['right_ankle']['position']

        stance_width = abs(right_ankle[0] - left_ankle[0])

        # 발가락 방향 (가능한 경우)
        foot_direction = "unknown"
        if 'left_big_toe' in foot and 'right_big_toe' in foot:
            left_toe = foot['left_big_toe']['position']
            right_toe = foot['right_big_toe']['position']

            # 발가락과 발목의 상대 위치로 발 방향 추정
            left_angle = math.degrees(math.atan2(left_toe[1] - left_ankle[1], left_toe[0] - left_ankle[0]))
            right_angle = math.degrees(math.atan2(right_toe[1] - right_ankle[1], right_toe[0] - right_ankle[0]))

            if abs(left_angle - right_angle) < 10:
                foot_direction = "평행"
            elif left_angle < right_angle:
                foot_direction = "팔자"
            else:
                foot_direction = "안짱"

        return {
            'width': stance_width,
            'type': "넓은 스탠스" if stance_width > 150 else "좁은 스탠스" if stance_width < 50 else "보통 스탠스",
            'foot_direction': foot_direction
        }

# 테스트 함수
def test_wholebody_analyzer():
    """Wholebody 분석기 테스트"""

    print("\n" + "="*60)
    print("RTMPose Wholebody Analyzer 테스트 (133 키포인트)")
    print("="*60)

    # 분석기 초기화
    analyzer = RTMPoseWholebodyAnalyzer(mode='balanced')

    # 테스트 이미지 로드
    test_image_path = Path("C:/try_angle/data/sample_images/mz1.jpg")

    if test_image_path.exists():
        from PIL import Image
        img = Image.open(test_image_path).convert('RGB')
        img_array = np.array(img)

        print(f"\n이미지 로드: {test_image_path.name}")
        print(f"크기: {img_array.shape}")

        # 133개 키포인트 추출
        print("\n[1] Wholebody 키포인트 추출...")
        wholebody_data = analyzer.extract_wholebody_keypoints(img_array)

        print(f"   감지된 사람: {wholebody_data['num_persons']}명")
        if wholebody_data['num_persons'] > 0:
            print(f"   바디 키포인트: {len(wholebody_data['body_keypoints'])}/17")
            print(f"   얼굴 랜드마크: {len(wholebody_data['face_landmarks'])}/68")
            print(f"   왼손 키포인트: {len(wholebody_data['left_hand'])}/21")
            print(f"   오른손 키포인트: {len(wholebody_data['right_hand'])}/21")
            print(f"   발 키포인트: {len(wholebody_data['foot_keypoints'])}/6")

            # 향상된 샷 타입 분석
            print("\n[2] 향상된 샷 타입 분석...")
            shot_type = analyzer.get_enhanced_shot_type(wholebody_data, img_array.shape[0])
            print(f"   타입: {shot_type['type']}")
            print(f"   설명: {shot_type['description']}")
            print(f"   커버리지: {shot_type['coverage']*100:.1f}%")
            print(f"   얼굴 랜드마크: {shot_type['face_landmarks_count']}개")
            print(f"   손 키포인트: {shot_type['hand_keypoints_count']}개")

            # 얼굴 방향 분석
            if len(wholebody_data['face_landmarks']) > 30:
                print("\n[3] 얼굴 방향 분석...")
                face_analysis = analyzer.analyze_face_direction(wholebody_data['face_landmarks'])
                for key, value in face_analysis.items():
                    print(f"   {key}: {value}")

            # 손 제스처 분석
            if len(wholebody_data['left_hand']) > 10:
                print("\n[4] 왼손 제스처 분석...")
                left_hand = analyzer.analyze_hand_gesture(wholebody_data['left_hand'], 'left')
                print(f"   제스처: {left_hand.get('gesture', 'unknown')}")
                print(f"   손가락 상태: {left_hand.get('fingers', {})}")

            if len(wholebody_data['right_hand']) > 10:
                print("\n[5] 오른손 제스처 분석...")
                right_hand = analyzer.analyze_hand_gesture(wholebody_data['right_hand'], 'right')
                print(f"   제스처: {right_hand.get('gesture', 'unknown')}")

            # 전신 자세 분석
            print("\n[6] 전신 자세 분석...")
            posture = analyzer.analyze_body_posture(wholebody_data)
            for key, value in posture.items():
                print(f"   {key}: {value}")


if __name__ == "__main__":
    test_wholebody_analyzer()