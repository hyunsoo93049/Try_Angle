"""
간단한 통합 테스트
작성일: 2025-12-05
"""

import os
import sys
import cv2
import numpy as np
import time

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.smart_feedback_v7 import SmartFeedbackV7
from realtime.frame_processor import FrameProcessor
from realtime.cache_manager import CacheManager

print("\n=== iOS 실시간 통합 시스템 간단 테스트 ===\n")

# 1. 시스템 초기화
print("1. 시스템 초기화")
feedback_system = SmartFeedbackV7(mode='ios', language='ko')
cache_manager = CacheManager()
frame_processor = FrameProcessor(
    feedback_system=feedback_system,
    cache_manager=cache_manager,
    enable_depth=True,
    enable_yolo=True
)
print("   - 초기화 완료\n")

# 2. 테스트 이미지 로드
test_image_path = r"C:\try_angle\data\sample_images\mz1.jpg"
print(f"2. 테스트 이미지 로드: {test_image_path}")

image = cv2.imread(test_image_path)
if image is None:
    print("   - 이미지 로드 실패!")
    sys.exit(1)

h, w = image.shape[:2]
print(f"   - 이미지 크기: {w}x{h}\n")

# 3. 워밍업
print("3. 모델 워밍업")
dummy = np.zeros((640, 640, 3), dtype=np.uint8)

# RTMPose
print("   - RTMPose 워밍업 중...")
for i in range(3):
    _ = feedback_system.wholebody.extract_wholebody_keypoints(dummy)
print("   - RTMPose 워밍업 완료")

# Depth
if frame_processor.depth_estimator:
    print("   - Depth 워밍업 중...")
    frame_processor.depth_estimator.warmup(dummy)
    print("   - Depth 워밍업 완료")

# YOLO
if frame_processor.yolo_detector:
    print("   - YOLO 워밍업 중...")
    frame_processor.yolo_detector.warmup(dummy)
    print("   - YOLO 워밍업 완료")

print()

# 4. 개별 모듈 테스트
print("4. 개별 모듈 테스트\n")

# RTMPose 테스트
print("   [RTMPose 테스트]")
start = time.perf_counter()
keypoints = feedback_system.wholebody.extract_wholebody_keypoints(image)
elapsed = (time.perf_counter() - start) * 1000
print(f"   - 처리 시간: {elapsed:.1f}ms")
if keypoints and keypoints.get('num_persons', 0) > 0:
    print(f"   - 검출된 사람: {keypoints['num_persons']}명")
    print(f"   - 키포인트 수: 133개")
else:
    print("   - 사람 검출 실패")

# Depth 테스트
if frame_processor.depth_estimator:
    print("\n   [Depth Anything 테스트]")
    start = time.perf_counter()
    depth_map = frame_processor.depth_estimator.process_frame(image)
    elapsed = (time.perf_counter() - start) * 1000

    if depth_map is not None:
        print(f"   - 처리 시간: {elapsed:.1f}ms")
        compression = frame_processor.depth_estimator.calculate_compression(depth_map)
        print(f"   - 압축감: {compression['compression_index']:.2f}")
        print(f"   - 카메라 타입: {compression['camera_type']}")
    else:
        print("   - Depth 추정 실패")

# YOLO 테스트
if frame_processor.yolo_detector:
    print("\n   [YOLO 테스트]")
    start = time.perf_counter()
    bbox = frame_processor.yolo_detector.detect_person(image)
    elapsed = (time.perf_counter() - start) * 1000

    if bbox:
        print(f"   - 처리 시간: {elapsed:.1f}ms")
        print(f"   - Person bbox: {bbox}")
    else:
        print("   - Person 검출 실패")

print()

# 5. 통합 프레임 처리 테스트
print("5. 통합 프레임 처리 테스트 (35프레임)\n")

times = []
for i in range(35):
    start = time.perf_counter()
    result = frame_processor.process_frame(image)
    elapsed = (time.perf_counter() - start) * 1000
    times.append(elapsed)

    # 매 10프레임마다 출력
    if i % 10 == 0:
        print(f"   프레임 {i}: {elapsed:.1f}ms")
        if result and result.get('feedback'):
            feedback = result['feedback']
            if feedback.get('primary'):
                print(f"      피드백: {feedback['primary']}")

# 6. 성능 통계
print(f"\n6. 성능 통계")
print(f"   - 총 프레임: {len(times)}")
print(f"   - 평균 시간: {sum(times)/len(times):.1f}ms")
print(f"   - 최대 시간: {max(times):.1f}ms")
print(f"   - 최소 시간: {min(times):.1f}ms")

fps_30_count = sum(1 for t in times if t < 33.3)
print(f"   - 30fps 달성률: {fps_30_count/len(times)*100:.1f}%")

if sum(times)/len(times) < 33.3:
    print("\n   [성공] 30fps 목표 달성!")
else:
    print(f"\n   [경고] 현재 FPS: {1000/(sum(times)/len(times)):.1f}")

print("\n=== 테스트 완료 ===")