#!/usr/bin/env python3
"""
압축감(Compression) 헬퍼 v2
더 관대한 점수, 상대적 표현 중심
"""

import math


def calculate_compression_score(diff: float) -> float:
    """
    압축감 차이를 점수로 변환 (더 관대하게)

    차이 0.05 → 95점
    차이 0.2 → 80점
    차이 0.4 → 65점
    차이 0.6 → 50점
    """
    if diff < 0.05:
        return 95
    elif diff < 0.2:
        # 0.05~0.2 구간: 95→80 (선형)
        return 95 - (diff - 0.05) * 100
    elif diff < 0.4:
        # 0.2~0.4 구간: 80→65 (더 완만하게)
        return 80 - (diff - 0.2) * 75
    else:
        # 0.4 이상: 최소 50점
        return max(50, 65 - (diff - 0.4) * 50)


def get_compression_intensity(diff: float) -> str:
    """압축감 차이를 강도로 표현"""
    if diff < 0.1:
        return "아주 조금"
    elif diff < 0.25:
        return "조금"
    elif diff < 0.4:
        return "어느 정도"
    else:
        return "꽤"


def describe_compression_simple(value: float) -> str:
    """압축감을 3단계로 단순 설명"""
    if value < 0.35:
        return "광각 쪽"
    elif value < 0.65:
        return "중간 정도"
    else:
        return "망원 쪽"


def check_shoulder_alignment(left_shoulder, right_shoulder) -> dict:
    """
    어깨 정렬 체크 (수평 기준 0도/180도)
    """
    dx = right_shoulder[0] - left_shoulder[0]
    dy = right_shoulder[1] - left_shoulder[1]

    # atan2는 -π to π (-180 to 180도)
    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)

    # 수평(0도 또는 180도)에서 벗어난 정도
    # 180도에 가까우면 180-angle, 0도에 가까우면 abs(angle)
    if abs(angle_deg) > 90:
        # 180도 근처 (-180 ~ -90 or 90 ~ 180)
        deviation = abs(abs(angle_deg) - 180)
    else:
        # 0도 근처 (-90 ~ 90)
        deviation = abs(angle_deg)

    # 판정
    if deviation < 5:
        return {
            'status': 'perfect',
            'angle': angle_deg,
            'deviation': deviation,
            'message': '어깨가 수평입니다 (좋음)',
            'needs_adjustment': False
        }
    elif deviation < 10:
        return {
            'status': 'good',
            'angle': angle_deg,
            'deviation': deviation,
            'message': '어깨가 거의 수평입니다',
            'needs_adjustment': False
        }
    elif deviation < 20:
        return {
            'status': 'slight_tilt',
            'angle': angle_deg,
            'deviation': deviation,
            'message': f'어깨가 약간 기울어져 있습니다 ({deviation:.0f}도)',
            'needs_adjustment': True
        }
    else:
        return {
            'status': 'tilted',
            'angle': angle_deg,
            'deviation': deviation,
            'message': f'어깨가 기울어져 있습니다 ({deviation:.0f}도)',
            'needs_adjustment': True
        }


def generate_compression_feedback(curr_comp: float, ref_comp: float) -> dict:
    """
    압축감 피드백 생성 (친절한 톤)
    """
    diff = abs(ref_comp - curr_comp)
    score = calculate_compression_score(diff)

    if diff < 0.05:
        return {
            'score': score,
            'match': True,
            'message': '압축감이 레퍼런스와 거의 일치합니다!',
            'actions': []
        }

    intensity = get_compression_intensity(diff)

    if curr_comp < ref_comp:
        # 현재가 더 광각
        return {
            'score': score,
            'match': False,
            'message': f'레퍼런스보다 {intensity} 광각 느낌입니다',
            'actions': [
                f'피사체에 {intensity} 더 가까이 가보세요',
                '또는 줌을 한 단계 더 확대해보세요'
            ],
            'technical': f'현재 {describe_compression_simple(curr_comp)}, 목표 {describe_compression_simple(ref_comp)}'
        }
    else:
        # 현재가 더 망원
        return {
            'score': score,
            'match': False,
            'message': f'레퍼런스보다 {intensity} 압축된 느낌입니다',
            'actions': [
                f'피사체에서 {intensity} 더 멀어져보세요',
                '또는 줌을 한 단계 축소해보세요'
            ],
            'technical': f'현재 {describe_compression_simple(curr_comp)}, 목표 {describe_compression_simple(ref_comp)}'
        }


def generate_final_summary(gates_result: dict) -> str:
    """
    최종 요약 코멘트 생성 (친절한 톤)
    """
    passed = []
    failed = []

    if 'aspect_ratio' in gates_result and gates_result['aspect_ratio']['passed']:
        passed.append('종횡비')
    elif 'aspect_ratio' in gates_result:
        failed.append('종횡비')

    if 'framing' in gates_result and gates_result['framing']['passed']:
        passed.append('샷 타입')
    elif 'framing' in gates_result:
        failed.append('샷 타입')

    if 'composition' in gates_result and gates_result['composition']['passed']:
        passed.append('구도')
    elif 'composition' in gates_result:
        failed.append('구도')

    if 'compression' in gates_result and gates_result['compression']['passed']:
        passed.append('압축감')
    elif 'compression' in gates_result:
        failed.append('압축감')

    # 요약 메시지
    if len(passed) >= 3 and len(failed) <= 1:
        if failed:
            return f"전반적으로 레퍼런스와 아주 비슷합니다! {failed[0]}만 살짝 조정하면 완벽할 것 같네요."
        else:
            return "완벽합니다! 레퍼런스와 거의 동일한 느낌이에요."
    elif len(passed) >= 2:
        return f"{', '.join(passed)}은(는) 레퍼런스와 잘 맞고, {', '.join(failed)}을(를) 조금 더 조정하면 좋을 것 같아요."
    else:
        return "레퍼런스와 차이가 있지만, 단계별로 조정하면 충분히 비슷해질 수 있습니다!"


def format_hand_detection_issue(curr_hands: int, ref_hands: int) -> str:
    """
    손 검출 이슈를 친절하게 설명
    """
    if ref_hands == 0 and curr_hands > 10:
        return "레퍼런스에서 손이 검출되지 않았습니다 (가려짐 또는 프레임 밖)"
    elif curr_hands == 0 and ref_hands > 10:
        return "현재 이미지에서 손이 검출되지 않았습니다 (조명 또는 각도 문제일 수 있음)"
    elif abs(curr_hands - ref_hands) > 10:
        return f"손 제스처 차이가 있을 수 있습니다 (검출: 현재 {curr_hands}개, 레퍼런스 {ref_hands}개)"
    else:
        return None