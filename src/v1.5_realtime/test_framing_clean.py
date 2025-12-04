#!/usr/bin/env python3
"""
프레이밍 분석 깔끔한 테스트 (디버그 출력 제거)
"""

import sys
import os
import warnings

# 경고 및 로그 억제
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# 경로 설정
sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

# stdout 임시 리다이렉트
import io
from contextlib import redirect_stdout, redirect_stderr

def analyze_quietly(comparer, current_path, reference_path):
    """조용히 분석 실행"""
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return comparer.analyze_with_gates(current_path, reference_path)

def main():
    """카페 사진 프레이밍 분석 (깔끔한 출력)"""

    print("\n" + "="*70)
    print(" " * 15 + "카페 사진 프레이밍 분석 결과")
    print("="*70)

    # 시스템 초기화 (조용히)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from compare_final_improved_v5_debug import SmartFeedbackV5Debug
        comparer = SmartFeedbackV5Debug()

    # 분석 실행
    print("\n분석 중...")
    result = analyze_quietly(comparer,
                            "data/sample_images/cafe4.jpg",  # 현재 (테이블 많이)
                            "data/sample_images/cafe3.jpg")  # 레퍼런스 (인물 위주)

    # 결과 출력
    if 'gates_result' in result and 'framing' in result['gates_result']:
        framing = result['gates_result']['framing']

        if 'details' in framing:
            details = framing['details']

            print("\n" + "-"*70)
            print(" " * 25 + "분석 결과")
            print("-"*70)

            # 1. 샷 타입
            shot = details['shot_type']
            print(f"\n[1] 샷 타입 비교")
            print(f"    cafe4 (현재):     {shot['current']['type']}")
            print(f"    cafe3 (레퍼런스): {shot['reference']['type']}")
            if shot['same_category']:
                print(f"    -> 같은 카테고리입니다 (점수: {shot['score']}점)")
            else:
                print(f"    -> 다른 카테고리입니다 (점수: {shot['score']}점)")

            # 2. 인물 비중
            subject = details['subject_ratio']
            print(f"\n[2] 인물이 화면에서 차지하는 비중")
            print(f"    cafe4 (현재):     {subject['current_ratio']:.1%}")
            print(f"    cafe3 (레퍼런스): {subject['reference_ratio']:.1%}")

            diff_percent = (subject['reference_ratio'] - subject['current_ratio']) * 100
            if subject['direction'] == 'smaller':
                print(f"    -> cafe4가 인물이 {abs(diff_percent):.0f}%p 더 작음 (점수: {subject['score']}점)")
            elif subject['direction'] == 'larger':
                print(f"    -> cafe4가 인물이 {abs(diff_percent):.0f}%p 더 큼 (점수: {subject['score']}점)")
            else:
                print(f"    -> 비슷한 수준 (점수: {subject['score']}점)")

            # 3. 테이블/하단 비중
            bottom = details['bottom_space']
            print(f"\n[3] 하단 공간(테이블) 비중")
            print(f"    cafe4 (현재):     {bottom['current_ratio']:.1%}")
            print(f"    cafe3 (레퍼런스): {bottom['reference_ratio']:.1%}")

            table_diff = (bottom['current_ratio'] - bottom['reference_ratio']) * 100
            if bottom['table_heavy']:
                print(f"    -> cafe4가 테이블이 {abs(table_diff):.0f}%p 더 많이 보임 (점수: {bottom['score']}점)")
            else:
                print(f"    -> 차이: {abs(table_diff):.0f}%p (점수: {bottom['score']}점)")

            # 종합 점수
            print(f"\n[4] 종합 프레이밍 점수: {details['overall_score']:.0f}/100")
            print(f"    (샷타입 30% + 인물비중 40% + 하단여백 30%)")

            # 생성된 피드백
            print("\n" + "-"*70)
            print(" " * 23 + "생성된 피드백")
            print("-"*70)

            feedback = details['feedback']
            print(f"\n심각도: {feedback['severity']}")
            print(f"요약: {feedback['summary']}")

            if feedback['actions']:
                print("\n권장 조정사항:")
                for i, action in enumerate(feedback['actions'], 1):
                    print(f"  {i}. {action}")

    # Gate System 전체 결과
    if 'gates_result' in result:
        print("\n" + "-"*70)
        print(" " * 23 + "Gate System 결과")
        print("-"*70)

        gates = result['gates_result']
        for gate_name in ['aspect_ratio', 'framing', 'composition', 'compression', 'pose_match']:
            if gate_name in gates and isinstance(gates[gate_name], dict):
                gate = gates[gate_name]
                status = "통과" if gate.get('passed', False) else "실패"
                score = gate.get('score', 0)
                print(f"  {gate_name:15s}: {status} ({score:.0f}점)")

    # 전체 점수
    if 'overall_score' in result:
        print(f"\n전체 유사도 점수: {result['overall_score']:.1f}/100")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()