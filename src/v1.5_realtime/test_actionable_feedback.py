#!/usr/bin/env python3
"""
액션 가능한 피드백 테스트
구체적인 움직임 지시를 테스트합니다.
"""

import sys
import os
import warnings

warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

from compare_final_improved_v5_debug import SmartFeedbackV5Debug

def test_actionable_feedback():
    """액션 가능한 피드백 테스트"""

    print("\n" + "="*70)
    print("액션 가능한 피드백 테스트")
    print("="*70)

    comparer = SmartFeedbackV5Debug()

    # 테스트 케이스 1: 카페 이미지 (더 나은 키포인트 감지)
    print("\n[테스트 1] 카페 이미지")
    print("  Current: cafe4.jpg")
    print("  Reference: cafe3.jpg")
    print("-"*50)

    result1 = comparer.analyze_with_gates(
        "data/sample_images/cafe4.jpg",
        "data/sample_images/cafe3.jpg"
    )

    # 액션 가능한 피드백 확인
    if 'all_gates' in result1:
        # 프레이밍 게이트 확인
        if 'framing' in result1['all_gates']:
            framing = result1['all_gates']['framing']
            if 'details' in framing:
                details = framing['details']

                # 액션 가능한 피드백 출력
                if 'actionable_feedback' in details:
                    actionable = details['actionable_feedback']
                    if actionable.get('has_actionable'):
                        print("\n[📸 액션 가능한 피드백 - 프레이밍]")
                        print(actionable['message'])

        # 구도 게이트 확인
        if 'composition' in result1['all_gates']:
            comp = result1['all_gates']['composition']
            if 'details' in comp and 'actionable_feedback' in comp['details']:
                actionable = comp['details']['actionable_feedback']
                if actionable.get('has_actionable'):
                    print("\n[📸 액션 가능한 피드백 - 구도]")
                    print(actionable['message'])

    # 테스트 케이스 2: 인물 사진
    print("\n\n[테스트 2] 인물 사진")
    print("  Current: mz1.jpg")
    print("  Reference: mz2.jpg")
    print("-"*50)

    result2 = comparer.analyze_with_gates(
        "data/sample_images/mz1.jpg",
        "data/sample_images/mz2.jpg"
    )

    # 액션 가능한 피드백 확인
    if 'all_gates' in result2:
        # 프레이밍 게이트 확인
        if 'framing' in result2['all_gates']:
            framing = result2['all_gates']['framing']
            if 'details' in framing:
                details = framing['details']

                # 액션 가능한 피드백 출력
                if 'actionable_feedback' in details:
                    actionable = details['actionable_feedback']
                    if actionable.get('has_actionable'):
                        print("\n[📸 액션 가능한 피드백 - 프레이밍]")
                        print(actionable['message'])

        # 구도 게이트 확인
        if 'composition' in result2['all_gates']:
            comp = result2['all_gates']['composition']
            if 'details' in comp and 'actionable_feedback' in comp['details']:
                actionable = comp['details']['actionable_feedback']
                if actionable.get('has_actionable'):
                    print("\n[📸 액션 가능한 피드백 - 구도]")
                    print(actionable['message'])

    # 최종 피드백 확인
    print("\n" + "="*70)
    print("최종 피드백")
    print("="*70)

    if 'friendly_summary' in result1:
        print(f"[카페] {result1['friendly_summary']}")

    if 'friendly_summary' in result2:
        print(f"[인물] {result2['friendly_summary']}")

    print("\n" + "="*70)

if __name__ == "__main__":
    test_actionable_feedback()