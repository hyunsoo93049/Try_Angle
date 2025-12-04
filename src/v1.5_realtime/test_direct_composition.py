#!/usr/bin/env python3
"""
구도 체크 직접 테스트
콘솔에 모든 출력 표시
"""

import sys
import os

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

print("\n" + "="*70)
print("구도 체크 직접 테스트")
print("="*70)

from compare_final_improved_v5_debug import SmartFeedbackV5Debug

comparer = SmartFeedbackV5Debug()

print("\n테스트: position_left.jpg vs position_right.jpg")
print("-"*50)

# 전체 디버그 출력 표시
result = comparer.analyze_with_gates(
    "data/test_images/position_left.jpg",
    "data/test_images/position_right.jpg"
)

print("\n" + "="*70)