#!/usr/bin/env python3
"""
뒷모습 인식 개선 테스트
파리 사진 (뒷모습) 테스트
"""

import sys
import os
import warnings

warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

from compare_final_improved_v5_debug import SmartFeedbackV5Debug

def test_back_view():
    """뒷모습 파리 사진 테스트"""

    print("\n" + "="*70)
    print("뒷모습 인식 개선 테스트")
    print("="*70)

    comparer = SmartFeedbackV5Debug()

    # 파리 사진 테스트
    print("\n[테스트] 파리 에펠탑 뒷모습 사진")
    print("  Current: Paris.jpg (야경)")
    print("  Reference: Paris1.jpg (주간)")

    result = comparer.analyze_with_gates(
        "data/sample_images/Paris.jpg",
        "data/sample_images/Paris1.jpg"
    )

    # 결과 확인
    if 'all_gates' in result and 'framing' in result['all_gates']:
        framing = result['all_gates']['framing']

        if 'details' in framing:
            details = framing['details']

            # 인물 방향 확인
            if 'person_orientation' in details:
                orient = details['person_orientation']
                print(f"\n[인물 방향 감지]")
                print(f"  Current: {orient['current'].get('direction', 'unknown')}")
                print(f"  Reference: {orient['reference'].get('direction', 'unknown')}")

            # 샷타입 확인
            shot = details['shot_type']
            print(f"\n[샷타입 분석]")
            print(f"  Current: {shot['current'].get('name_kr', shot['current'].get('type', 'unknown'))}")
            print(f"  Reference: {shot['reference'].get('name_kr', shot['reference'].get('type', 'unknown'))}")

            # 4방향 여백
            if 'all_margins' in details:
                margins = details['all_margins']
                print(f"\n[4방향 여백]")

                curr_m = margins['current']
                ref_m = margins['reference']

                print(f"  Current: 상{curr_m['top']*100:.0f}% 하{curr_m['bottom']*100:.0f}% " +
                      f"좌{curr_m['left']*100:.0f}% 우{curr_m['right']*100:.0f}%")
                print(f"  Reference: 상{ref_m['top']*100:.0f}% 하{ref_m['bottom']*100:.0f}% " +
                      f"좌{ref_m['left']*100:.0f}% 우{ref_m['right']*100:.0f}%")

            # 전체 점수
            print(f"\n프레이밍 점수: {details.get('overall_score', 0):.0f}/100")

    # 친절한 피드백
    if 'friendly_summary' in result:
        print(f"\n[피드백]")
        print(f"  {result['friendly_summary']}")

    print("\n" + "="*70)

if __name__ == "__main__":
    test_back_view()