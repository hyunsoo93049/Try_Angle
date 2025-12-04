#!/usr/bin/env python3
"""
최종 구체적 움직임 피드백 테스트
실제 이미지로 구도 체크 시 움직임 지시 확인
"""

import sys
import os
import warnings

warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

from compare_final_improved_v5_debug import SmartFeedbackV5Debug
import io
from contextlib import redirect_stdout, redirect_stderr

def capture_composition_output(comparer, img1, img2):
    """구도 체크 출력만 캡처"""

    # 분석 실행
    result = comparer.analyze_with_gates(img1, img2)

    return result

def main():
    print("\n" + "="*70)
    print("최종 구체적 움직임 피드백 테스트")
    print("="*70)

    # 시스템 초기화 (조용히)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        comparer = SmartFeedbackV5Debug()

    # 테스트 1: 인위적으로 만든 위치 차이
    print("\n[테스트 1] 위치 이동 테스트")
    print("  Current: position_left.jpg (인물 왼쪽)")
    print("  Reference: position_right.jpg (인물 오른쪽)")
    print("-"*50)

    with redirect_stdout(io.StringIO()):
        result1 = capture_composition_output(
            comparer,
            "data/test_images/position_left.jpg",
            "data/test_images/position_right.jpg"
        )

    if 'all_gates' in result1:
        for gate_name in ['framing', 'composition']:
            if gate_name in result1['all_gates']:
                gate_data = result1['all_gates'][gate_name]
                print(f"\n[{gate_name.upper()}]")
                print(f"  점수: {gate_data.get('score', 0):.0f}/100")

                # 상세 정보에서 구체적 움직임 찾기
                if 'details' in gate_data:
                    details = gate_data['details']

                    # 프레이밍의 actionable_feedback
                    if gate_name == 'framing' and 'actionable_feedback' in details:
                        feedback = details['actionable_feedback']
                        if feedback.get('message'):
                            print(f"\n  [구체적 조정 방법]")
                            for line in feedback['message'].split('\n'):
                                if line.strip():
                                    print(f"  {line}")

    # 테스트 2: 실제 이미지 (카페)
    print("\n\n[테스트 2] 카페 이미지")
    print("  Current: cafe1.jpg")
    print("  Reference: cafe3.jpg")
    print("-"*50)

    with redirect_stdout(io.StringIO()):
        result2 = capture_composition_output(
            comparer,
            "data/sample_images/cafe1.jpg",
            "data/sample_images/cafe3.jpg"
        )

    if 'all_gates' in result2:
        if 'composition' in result2['all_gates']:
            comp = result2['all_gates']['composition']
            print(f"\n[COMPOSITION]")
            print(f"  점수: {comp.get('score', 0):.0f}/100")

    # 최종 요약
    print("\n" + "="*70)
    print("최종 요약")
    print("="*70)

    if 'friendly_summary' in result1:
        print(f"[테스트 1] {result1['friendly_summary']}")

    if 'friendly_summary' in result2:
        print(f"[테스트 2] {result2['friendly_summary']}")

if __name__ == "__main__":
    main()