#!/usr/bin/env python3
"""
SmartFeedbackV5 깔끔한 테스트 (디버그 출력 없이)
"""

import sys
import os
import warnings

# 경고 억제
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# 경로 설정
sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

from compare_final_improved_v5 import SmartFeedbackV5

def test_v5():
    """V5 테스트 (피드백만 출력)"""

    print("\n" + "="*60)
    print("SmartFeedbackV5 - 프레이밍 분석 테스트")
    print("="*60)

    # 시스템 초기화
    comparer = SmartFeedbackV5(language='ko')

    # 테스트할 이미지 쌍들
    test_pairs = [
        ("cafe4.jpg", "cafe3.jpg", "카페 사진 (테이블 많음 vs 인물 중심)"),
        # ("mz1.jpg", "mz2.jpg", "MZ 테스트"),
        # ("shtest1.jpg", "shtest2.jpg", "SH 테스트"),
    ]

    for curr, ref, description in test_pairs:
        curr_path = f"data/sample_images/{curr}"
        ref_path = f"data/sample_images/{ref}"

        print(f"\n[테스트] {description}")
        print(f"  현재: {curr}")
        print(f"  레퍼런스: {ref}")
        print("-" * 40)

        # 분석 실행
        result = comparer.analyze_with_gates(
            curr_path,
            ref_path,
            test_mode=True  # 모든 Gate 분석
        )

        # 결과 출력
        if 'all_gates' in result:
            gates = result['all_gates']

            # 프레이밍 결과
            if 'framing' in gates:
                framing = gates['framing']
                print(f"\n프레이밍 점수: {framing['score']:.0f}/100")

                if framing.get('feedback'):
                    feedback = framing['feedback']

                    # 샷 타입 정보
                    if 'shot_type' in feedback:
                        shot = feedback['shot_type']
                        print(f"  샷 타입: {shot['current']['type']} → {shot['reference']['type']}")
                        if shot['same_category']:
                            print(f"    (같은 카테고리)")

                    # 인물 비중 정보
                    if 'subject_ratio' in feedback:
                        subj = feedback['subject_ratio']
                        print(f"  인물 비중: {subj['current_ratio']*100:.0f}% → {subj['reference_ratio']*100:.0f}%")

                    # 하단 공간 정보
                    if 'bottom_space' in feedback:
                        bottom = feedback['bottom_space']
                        print(f"  하단 공간: {bottom['current_ratio']*100:.0f}% → {bottom['reference_ratio']*100:.0f}%")

                    # 액션 아이템
                    if 'actions' in feedback and feedback['actions']:
                        print(f"\n  권장 조정:")
                        for i, action in enumerate(feedback['actions'], 1):
                            print(f"    {i}. {action}")

            # 다른 Gate 점수 요약
            print(f"\n[Gate 점수 요약]")
            for gate_name in ['aspect_ratio', 'framing', 'composition', 'compression']:
                if gate_name in gates:
                    gate = gates[gate_name]
                    status = "✓" if gate.get('passed', False) else "✗"
                    print(f"  {gate_name:15s}: {gate.get('score', 0):3.0f}점 {status}")

        # 전체 점수
        if 'overall_score' in result:
            print(f"\n전체 유사도: {result['overall_score']:.1f}/100")

        # 최종 피드백
        if 'friendly_summary' in result:
            print(f"\n[최종 피드백]")
            print(f"  {result['friendly_summary']}")

    print("\n" + "="*60)

if __name__ == "__main__":
    test_v5()