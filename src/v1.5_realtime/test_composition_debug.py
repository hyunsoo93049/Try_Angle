#!/usr/bin/env python3
"""
구도 체크 디버깅
"""

import sys
import os
import io

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

from compare_final_improved_v5_debug import SmartFeedbackV5Debug
import cv2

def test():
    comparer = SmartFeedbackV5Debug()

    # 실제 이미지 로드
    img1 = cv2.imread("data/test_images/position_left.jpg")
    img2 = cv2.imread("data/test_images/position_right.jpg")

    # 키포인트 추출
    curr_kpts = comparer.wholebody.extract_wholebody_keypoints(img1)
    ref_kpts = comparer.wholebody.extract_wholebody_keypoints(img2)

    curr_shape = img1.shape
    ref_shape = img2.shape

    print("\n[구도 체크 디버그]")
    print("="*50)

    # 얼굴 중심 계산
    curr_center = comparer._calculate_face_center(curr_kpts, curr_shape)
    ref_center = comparer._calculate_face_center(ref_kpts, ref_shape)

    if curr_center and ref_center:
        print(f"Current 중심: ({curr_center[0]:.2f}, {curr_center[1]:.2f})")
        print(f"Reference 중심: ({ref_center[0]:.2f}, {ref_center[1]:.2f})")

        x_diff = ref_center[0] - curr_center[0]
        y_diff = ref_center[1] - curr_center[1]

        print(f"\n차이: x={x_diff:.2f}, y={y_diff:.2f}")

        # 구체적 움직임 계산
        if abs(x_diff) > 0.05:
            percent_x = abs(x_diff) * 100
            if x_diff > 0:
                print(f"\n📸 카메라를 왼쪽으로 {percent_x:.0f}% 이동")
                steps = comparer._to_steps_simple(percent_x)
                print(f"   또는 인물이 오른쪽으로 {steps} 이동")
            else:
                print(f"\n📸 카메라를 오른쪽으로 {percent_x:.0f}% 이동")
                steps = comparer._to_steps_simple(percent_x)
                print(f"   또는 인물이 왼쪽으로 {steps} 이동")

        if abs(y_diff) > 0.05:
            percent_y = abs(y_diff) * 100
            angle = min(int(percent_y * 0.5), 15)
            if y_diff > 0:
                print(f"\n📸 카메라를 {angle}도 아래로 틸트")
            else:
                print(f"\n📸 카메라를 {angle}도 위로 틸트")

    else:
        print("얼굴 중심 검출 실패")

if __name__ == "__main__":
    test()