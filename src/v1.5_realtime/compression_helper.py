#!/usr/bin/env python3
"""
압축감(Compression) 헬퍼 함수
상대적 비교 중심으로 개선
"""

def interpret_compression_relative(curr_comp: float, ref_comp: float) -> dict:
    """
    압축감을 상대적으로 해석
    절대 배율 변환 없이 방향성만 제공
    """

    diff = ref_comp - curr_comp

    # 압축감 구간 해석 (절대값 아닌 설명)
    def describe_compression(value):
        if value < 0.3:
            return "광각 느낌 (배경이 넓게 퍼짐)"
        elif value < 0.5:
            return "표준 느낌 (자연스러운 거리감)"
        elif value < 0.7:
            return "약간의 압축감"
        else:
            return "망원 느낌 (배경 압축)"

    # 조정 방향 (구체적 배율 없이)
    actions = []

    if abs(diff) < 0.05:
        # 거의 같음
        return {
            'match': True,
            'current_desc': describe_compression(curr_comp),
            'target_desc': describe_compression(ref_comp),
            'actions': ["압축감이 적절합니다"]
        }

    if curr_comp < ref_comp:
        # 현재가 더 광각 → 압축감 늘려야 함
        intensity = "조금" if abs(diff) < 0.2 else "좀 더"

        actions.append(f"레퍼런스보다 압축감이 약합니다")
        actions.append(f"피사체에 {intensity} 가까이 가세요")
        actions.append(f"또는 줌을 {intensity} 확대하세요")

    else:
        # 현재가 더 망원 → 압축감 줄여야 함
        intensity = "조금" if abs(diff) < 0.2 else "좀 더"

        actions.append(f"레퍼런스보다 압축감이 강합니다")
        actions.append(f"피사체에서 {intensity} 멀어지세요")
        actions.append(f"또는 줌을 {intensity} 축소하세요")

    return {
        'match': False,
        'current_desc': describe_compression(curr_comp),
        'target_desc': describe_compression(ref_comp),
        'current_value': curr_comp,
        'target_value': ref_comp,
        'difference': diff,
        'actions': actions
    }


def estimate_distance_change(compression_diff: float) -> str:
    """
    압축감 차이를 거리 변화로 추정
    배율 대신 상대적 거리만 제안
    """

    abs_diff = abs(compression_diff)

    if abs_diff < 0.05:
        return "거의 같은 위치"
    elif abs_diff < 0.15:
        return "한두 걸음"
    elif abs_diff < 0.3:
        return "서너 걸음"
    else:
        return "상당한 거리"


def get_compression_feedback(curr_comp: float, ref_comp: float) -> str:
    """
    사용자 친화적인 압축감 피드백 생성
    """

    result = interpret_compression_relative(curr_comp, ref_comp)

    if result['match']:
        return "✓ 압축감이 레퍼런스와 일치합니다"

    feedback = []
    feedback.append(f"현재: {result['current_desc']} ({curr_comp:.2f})")
    feedback.append(f"목표: {result['target_desc']} ({ref_comp:.2f})")
    feedback.append("")
    feedback.append("[조정 방법]")

    for action in result['actions']:
        feedback.append(f"• {action}")

    # 거리 추정 추가
    distance = estimate_distance_change(result['difference'])
    if distance != "거의 같은 위치":
        feedback.append(f"• 예상 이동 거리: {distance}")

    return "\n".join(feedback)


# 압축감 개념 설명 (사용자 교육용)
COMPRESSION_EXPLANATION = """
## 압축감(Compression)이란?

배경과 피사체 사이의 거리감을 나타내는 값입니다.

### 압축감 구간:
• 0.0~0.3: 광각 효과 - 배경이 멀고 넓게 보임
• 0.3~0.5: 표준 - 자연스러운 거리감
• 0.5~0.7: 약간의 압축 - 배경이 조금 가까워 보임
• 0.7~1.0: 망원 효과 - 배경이 압축되어 가까이 보임

### 조정 방법:
• 압축감을 늘리려면: 피사체에 가까이 가거나 줌인
• 압축감을 줄이려면: 피사체에서 멀어지거나 줌아웃

※ 현재는 레퍼런스와의 상대 비교로 방향을 안내합니다.
※ 정확한 줌 배율은 추후 캘리브레이션 예정입니다.
"""