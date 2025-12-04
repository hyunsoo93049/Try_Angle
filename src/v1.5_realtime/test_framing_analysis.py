#!/usr/bin/env python3
"""
프레이밍 분석 테스트
cafe3 vs cafe4로 테이블/인물 비율 분석 검증
"""

import sys
import os

# 경로 설정
sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

from compare_final_improved_v5_debug import SmartFeedbackV5Debug

def test_framing_analysis():
    """cafe3 vs cafe4 프레이밍 분석 테스트"""

    print("="*50)
    print("프레이밍 분석 테스트: cafe3 vs cafe4")
    print("="*50)

    comparer = SmartFeedbackV5Debug()

    # cafe3 (사람 위주) vs cafe4 (테이블 많이 보임)
    print("\n[테스트 1] cafe3 (레퍼런스) vs cafe4 (현재)")
    print("예상: cafe4가 테이블이 더 많이 보이고, 인물 비중이 작음")

    result = comparer.analyze_with_gates(
        "data/sample_images/cafe4.jpg",  # 현재 (테이블 많이 보임)
        "data/sample_images/cafe3.jpg"   # 레퍼런스 (사람 위주)
    )

    # Gate System 결과 확인
    if 'gates_result' in result:
        gates = result['gates_result']

        # 프레이밍 게이트 상세 확인
        if 'framing' in gates:
            framing = gates['framing']
            print(f"\n프레이밍 점수: {framing['score']:.1f}")
            print(f"통과 여부: {framing['passed']}")

            # 상세 분석 결과
            if 'details' in framing:
                details = framing['details']

                # 샷 타입 비교
                print(f"\n[샷 타입]")
                print(f"  현재: {details['shot_type']['current']['type']}")
                print(f"  레퍼런스: {details['shot_type']['reference']['type']}")
                print(f"  같은 카테고리: {details['shot_type']['same_category']}")

                # 인물 비중
                print(f"\n[인물 비중]")
                print(f"  현재: {details['subject_ratio']['current_ratio']:.2%}")
                print(f"  레퍼런스: {details['subject_ratio']['reference_ratio']:.2%}")
                print(f"  방향: {details['subject_ratio']['direction']}")

                # 하단 여백 (테이블)
                print(f"\n[하단 여백/테이블]")
                print(f"  현재: {details['bottom_space']['current_ratio']:.2%}")
                print(f"  레퍼런스: {details['bottom_space']['reference_ratio']:.2%}")
                print(f"  테이블 위주: {details['bottom_space']['table_heavy']}")

                # 피드백
                print(f"\n[피드백]")
                feedback = details['feedback']
                print(f"  심각도: {feedback['severity']}")
                print(f"  요약: {feedback['summary']}")
                if feedback['actions']:
                    print(f"  조치사항:")
                    for action in feedback['actions']:
                        print(f"    - {action}")

            # 피드백 메시지 확인
            if 'feedback' in framing:
                print(f"\n[최종 피드백]")
                print(f"  {framing['feedback']}")

    print("\n" + "="*50)

    # 반대로도 테스트
    print("\n[테스트 2] cafe4 (레퍼런스) vs cafe3 (현재)")
    print("예상: cafe3이 인물 비중이 더 크고, 테이블이 적게 보임")

    result2 = comparer.analyze_with_gates(
        "data/sample_images/cafe3.jpg",  # 현재 (사람 위주)
        "data/sample_images/cafe4.jpg"   # 레퍼런스 (테이블 많이 보임)
    )

    if 'gates_result' in result2:
        gates2 = result2['gates_result']

        if 'framing' in gates2:
            framing2 = gates2['framing']
            print(f"\n프레이밍 점수: {framing2['score']:.1f}")

            if 'details' in framing2:
                details2 = framing2['details']

                # 인물 비중 비교
                print(f"\n[인물 비중]")
                print(f"  현재: {details2['subject_ratio']['current_ratio']:.2%}")
                print(f"  레퍼런스: {details2['subject_ratio']['reference_ratio']:.2%}")
                print(f"  방향: {details2['subject_ratio']['direction']}")

                # 하단 여백 비교
                print(f"\n[하단 여백/테이블]")
                print(f"  현재: {details2['bottom_space']['current_ratio']:.2%}")
                print(f"  레퍼런스: {details2['bottom_space']['reference_ratio']:.2%}")

                # 피드백
                if 'feedback' in framing2:
                    print(f"\n[피드백]")
                    print(f"  {framing2['feedback']}")

    print("\n테스트 완료!")


if __name__ == "__main__":
    test_framing_analysis()