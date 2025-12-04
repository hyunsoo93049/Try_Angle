#!/usr/bin/env python3
"""
개선사항 테스트
- 샷타입 한글명
- bust/medium 관대하게, knee/full 엄격하게
- 피드백 일관성
"""

import sys
import os
import warnings

warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

# Redirect output
import io
from contextlib import redirect_stdout, redirect_stderr

def main():
    print("\n" + "="*70)
    print("프레이밍 개선사항 테스트")
    print("="*70)

    # 시스템 초기화 (조용히)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from compare_final_improved_v5_debug import SmartFeedbackV5Debug
        comparer = SmartFeedbackV5Debug()

        # cafe 이미지 분석
        result = comparer.analyze_with_gates(
            "data/sample_images/cafe4.jpg",
            "data/sample_images/cafe3.jpg"
        )

    # 결과 검증
    if 'all_gates' in result and 'framing' in result['all_gates']:
        framing = result['all_gates']['framing']

        if 'details' in framing:
            details = framing['details']

            print("\n[1] 샷타입 한글명 확인")
            print("-" * 40)
            shot = details['shot_type']
            curr_kr = shot['current'].get('name_kr', 'N/A')
            ref_kr = shot['reference'].get('name_kr', 'N/A')

            print(f"현재: {curr_kr} ({shot['current']['type']})")
            print(f"레퍼런스: {ref_kr} ({shot['reference']['type']})")
            print(f"같은 카테고리: {shot['same_category']}")
            print(f"점수: {shot['score']}/100")

            # bust/medium 관대함 확인
            if shot['current']['type'] in ['bust_shot', 'medium_shot'] and \
               shot['reference']['type'] in ['bust_shot', 'medium_shot']:
                if shot['same_category'] and shot['score'] == 75:
                    print("✓ bust/medium 관대하게 처리됨 (75점)")
                else:
                    print(f"✗ bust/medium 점수 이상 ({shot['score']}점)")

            print("\n[2] 인물/테이블 비중")
            print("-" * 40)
            subj = details['subject_ratio']
            bottom = details['bottom_space']

            print(f"인물 비중: {subj['current_ratio']*100:.1f}% vs {subj['reference_ratio']*100:.1f}%")
            print(f"하단 공간: {bottom['current_ratio']*100:.1f}% vs {bottom['reference_ratio']*100:.1f}%")

            print("\n[3] 피드백 일관성 확인")
            print("-" * 40)
            feedback = details['feedback']

            print(f"심각도: {feedback['severity']}")
            print(f"요약: {feedback['summary']}")

            if feedback['friendly_message']:
                print("\n친근한 메시지:")
                for sentence in feedback['friendly_message'].split('. '):
                    if sentence.strip():
                        print(f"  • {sentence.strip()}")

            # 모순 검사
            print("\n[4] 모순 검사")
            print("-" * 40)

            overall_score = details['overall_score']
            if overall_score < 70:
                if "잘 맞습니다" in feedback.get('friendly_message', ''):
                    print("✗ 모순: 점수가 낮은데 '잘 맞는다'고 나옴")
                else:
                    print("✓ 일관성 있음: 낮은 점수에 개선 필요 피드백")
            else:
                print(f"✓ 점수 {overall_score}/100 - 적절한 수준")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()