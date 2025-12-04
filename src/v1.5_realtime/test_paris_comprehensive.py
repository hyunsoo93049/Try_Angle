#!/usr/bin/env python3
"""
파리 사진 종합 조정 가이드 테스트
"""

import sys
import os
import io

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

# 시스템 메시지 숨기기
from contextlib import redirect_stdout, redirect_stderr

def main():
    print("\n" + "="*70)
    print("파리 사진 종합 조정 가이드 테스트")
    print("="*70)

    # 시스템 초기화 (조용히)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from compare_final_improved_v5_debug import SmartFeedbackV5Debug
        comparer = SmartFeedbackV5Debug()

    print("\n[테스트 이미지]")
    print("  Current: Paris.jpg (인물 왼쪽, 에펠탑 야경)")
    print("  Reference: Paris1.jpg (인물 중앙쪽, 에펠탑 주간)")
    print("-"*50)

    # 분석 실행
    result = comparer.analyze_with_gates(
        "data/sample_images/Paris.jpg",
        "data/sample_images/Paris1.jpg"
    )

    # 주요 결과 추출
    if 'all_gates' in result:
        # 구도
        if 'composition' in result['all_gates']:
            comp = result['all_gates']['composition']
            print(f"\n[구도]")
            print(f"  점수: {comp.get('score', 0):.0f}/100")

        # 프레이밍
        if 'framing' in result['all_gates']:
            framing = result['all_gates']['framing']
            print(f"\n[프레이밍]")
            print(f"  점수: {framing.get('score', 0):.0f}/100")

            # 종합 가이드 확인
            if 'details' in framing:
                details = framing['details']

                # 종합 움직임 가이드
                if 'comprehensive_guide' in details:
                    guide = details['comprehensive_guide']
                    if guide.get('movements'):
                        print(f"\n[종합 조정 가이드]")
                        print("-"*50)
                        for move in guide['movements']:
                            print(f"  {move['step']}단계: {move['instruction']}")
                            if 'alternative' in move:
                                print(f"         또는 {move['alternative']}")
                            if 'effect' in move:
                                print(f"         효과: {move['effect']}")

                # 샷타입 정보
                if 'shot_type' in details:
                    shot = details['shot_type']
                    print(f"\n[샷타입]")
                    print(f"  현재: {shot['current'].get('name_kr', shot['current']['type'])}")
                    print(f"  목표: {shot['reference'].get('name_kr', shot['reference']['type'])}")

        # 압축감
        if 'compression' in result['all_gates']:
            comp_data = result['all_gates']['compression']
            print(f"\n[압축감]")
            print(f"  점수: {comp_data.get('score', 0):.0f}/100")

    # 최종 피드백
    if 'friendly_summary' in result:
        print(f"\n[최종 피드백]")
        print(f"  {result['friendly_summary']}")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()