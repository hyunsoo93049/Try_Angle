#!/usr/bin/env python3
"""
프레이밍 분석 간단 테스트
"""

import sys
import os

# 경로 설정
sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

from compare_final_improved_v5_debug import SmartFeedbackV5Debug

def test_cafe_photos():
    """카페 사진 프레이밍 분석"""

    print("\n" + "="*60)
    print("카페 사진 프레이밍 분석 - 인물/테이블 비중 차이")
    print("="*60)

    comparer = SmartFeedbackV5Debug()

    # cafe3 (사람 위주) vs cafe4 (테이블 많이)
    result = comparer.analyze_with_gates(
        "data/sample_images/cafe4.jpg",  # 현재
        "data/sample_images/cafe3.jpg"   # 레퍼런스
    )

    # 결과 출력
    if 'gates_result' in result and 'framing' in result['gates_result']:
        framing = result['gates_result']['framing']
        if 'details' in framing:
            details = framing['details']

            print("\n[프레이밍 분석 결과]")
            print("-" * 40)

            # 샷 타입
            shot = details['shot_type']
            print(f"샷 타입:")
            print(f"  - cafe4: {shot['current']['type']}")
            print(f"  - cafe3: {shot['reference']['type']}")
            print(f"  - 같은 카테고리: {shot['same_category']}")

            # 인물 비중
            subject = details['subject_ratio']
            print(f"\n인물 비중:")
            print(f"  - cafe4: {subject['current_ratio']:.1%} (테이블 위주)")
            print(f"  - cafe3: {subject['reference_ratio']:.1%} (인물 위주)")
            diff_percent = abs(subject['reference_ratio'] - subject['current_ratio']) * 100
            print(f"  - 차이: {diff_percent:.0f}%p")

            # 하단 여백
            bottom = details['bottom_space']
            print(f"\n하단 여백 (테이블):")
            print(f"  - cafe4: {bottom['current_ratio']:.1%}")
            print(f"  - cafe3: {bottom['reference_ratio']:.1%}")
            table_diff = abs(bottom['current_ratio'] - bottom['reference_ratio']) * 100
            print(f"  - 차이: {table_diff:.0f}%p")

            # 종합 점수
            print(f"\n종합 프레이밍 점수: {details['overall_score']:.0f}/100")

            # 피드백
            print(f"\n[생성된 피드백]")
            print("-" * 40)
            feedback = details['feedback']
            for action in feedback['actions']:
                print(f"  - {action}")

    print("\n" + "="*60)

    # 전체 점수
    if 'overall_score' in result:
        print(f"\n전체 유사도: {result['overall_score']:.1f}/100")

    # Gate 결과
    if 'gates_result' in result:
        gates = result['gates_result']
        passed = [name for name, g in gates.items() if isinstance(g, dict) and g.get('passed', False)]
        failed = [name for name, g in gates.items() if isinstance(g, dict) and not g.get('passed', False)]
        print(f"\n[Gate System 결과]")
        print(f"통과한 게이트: {', '.join(passed) if passed else '없음'}")
        print(f"실패한 게이트: {', '.join(failed) if failed else '없음'}")

if __name__ == "__main__":
    # 로그 억제
    import warnings
    warnings.filterwarnings("ignore")

    test_cafe_photos()