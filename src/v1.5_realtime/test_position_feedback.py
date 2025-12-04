#!/usr/bin/env python3
"""
위치 피드백 테스트
구도가 다른 이미지를 테스트합니다.
"""

import sys
import os
import warnings
import io

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

# Direct test of framing analyzer
from framing_analyzer import FramingAnalyzer
import numpy as np

def create_test_keypoints(face_x, face_y):
    """테스트용 키포인트 생성"""
    return {
        'num_persons': 1,
        'face_landmarks': {
            'nose': {
                'position': [face_x * 100, face_y * 100],
                'confidence': 0.9
            },
            'left_eye': {
                'position': [(face_x - 0.02) * 100, face_y * 100],
                'confidence': 0.9
            },
            'right_eye': {
                'position': [(face_x + 0.02) * 100, face_y * 100],
                'confidence': 0.9
            }
        },
        'body_keypoints': {
            'head': {
                'position': [face_x * 100, face_y * 100],
                'confidence': 0.9
            },
            'left_shoulder': {
                'position': [(face_x - 0.1) * 100, (face_y + 0.1) * 100],
                'confidence': 0.8
            },
            'right_shoulder': {
                'position': [(face_x + 0.1) * 100, (face_y + 0.1) * 100],
                'confidence': 0.8
            }
        }
    }

def test_position_movements():
    """위치 움직임 피드백 테스트"""

    print("\n" + "="*70)
    print("위치 기반 움직임 피드백 테스트")
    print("="*70)

    analyzer = FramingAnalyzer()

    # 테스트 케이스 1: 왼쪽에서 오른쪽으로
    print("\n[테스트 1] 왼쪽 → 오른쪽 이동")
    print("-"*50)

    curr_kpts = create_test_keypoints(0.3, 0.5)  # 왼쪽
    ref_kpts = create_test_keypoints(0.7, 0.5)   # 오른쪽
    shape = (100, 100)  # 이미지 크기

    # 위치 움직임 분석
    position_movements = analyzer._analyze_position_movements(
        curr_kpts, ref_kpts, shape, shape
    )

    # 여백 조정 분석
    margin_data = {
        'current': {'left': 0.2, 'right': 0.5, 'top': 0.3, 'bottom': 0.3},
        'reference': {'left': 0.5, 'right': 0.2, 'top': 0.3, 'bottom': 0.3},
        'differences': {'left': 0.3, 'right': 0.3, 'top': 0.0, 'bottom': 0.0}
    }
    margin_adjustments = analyzer._margin_to_adjustments(margin_data)

    # 액션 가능한 피드백 생성
    actionable_feedback = analyzer.generate_actionable_feedback(
        position_movements, margin_adjustments, 45  # 낮은 점수
    )

    print("현재 위치:", position_movements['grid_info']['current']['name'])
    print("목표 위치:", position_movements['grid_info']['target']['name'])
    print("\n[생성된 피드백]")
    print(actionable_feedback['message'])

    # 테스트 케이스 2: 위에서 아래로
    print("\n\n[테스트 2] 위 → 아래 이동")
    print("-"*50)

    curr_kpts = create_test_keypoints(0.5, 0.2)  # 위
    ref_kpts = create_test_keypoints(0.5, 0.7)   # 아래

    position_movements = analyzer._analyze_position_movements(
        curr_kpts, ref_kpts, shape, shape
    )

    actionable_feedback = analyzer.generate_actionable_feedback(
        position_movements, [], 50
    )

    print("현재 위치:", position_movements['grid_info']['current']['name'])
    print("목표 위치:", position_movements['grid_info']['target']['name'])
    print("\n[생성된 피드백]")
    print(actionable_feedback['message'])

    # 테스트 케이스 3: 대각선 이동
    print("\n\n[테스트 3] 좌측 상단 → 우측 하단")
    print("-"*50)

    curr_kpts = create_test_keypoints(0.2, 0.2)  # 좌측 상단
    ref_kpts = create_test_keypoints(0.8, 0.8)   # 우측 하단

    position_movements = analyzer._analyze_position_movements(
        curr_kpts, ref_kpts, shape, shape
    )

    actionable_feedback = analyzer.generate_actionable_feedback(
        position_movements, [], 40
    )

    print("현재 위치:", position_movements['grid_info']['current']['name'])
    print("목표 위치:", position_movements['grid_info']['target']['name'])
    print("\n[생성된 피드백]")
    print(actionable_feedback['message'])

    # 움직임 상세 정보
    print("\n\n[움직임 상세 정보]")
    print("-"*50)
    for i, move in enumerate(position_movements['movements'], 1):
        print(f"\n움직임 {i}:")
        print(f"  타입: {move['type']}")
        print(f"  방향: {move['direction']}")
        print(f"  카메라: {move['camera_action']}")
        print(f"  인물: {move['subject_action']}")
        print(f"  우선순위: {move['priority']}")

    print("\n" + "="*70)

if __name__ == "__main__":
    test_position_movements()