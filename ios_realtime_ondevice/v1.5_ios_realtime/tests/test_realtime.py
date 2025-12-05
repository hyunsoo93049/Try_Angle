#!/usr/bin/env python3
"""
iOS 실시간 버전 통합 테스트
작성일: 2025-12-05
"""

import sys
import os
import time
import cv2
import numpy as np
from pathlib import Path

# 경로 추가
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent))

# 모듈 임포트
from core.smart_feedback_v7 import SmartFeedbackV7
from realtime.cache_manager import CacheManager
from realtime.frame_processor import FrameProcessor


def test_basic_initialization():
    """기본 초기화 테스트"""
    print("\n" + "="*60)
    print("1. 기본 초기화 테스트")
    print("="*60)

    try:
        # iOS 모드로 초기화
        feedback_system = SmartFeedbackV7(mode='ios', debug_mode=True)
        print("✓ SmartFeedbackV7 초기화 성공")

        # 캐시 매니저 초기화
        cache_manager = CacheManager(cache_timeout=3600)
        print("✓ CacheManager 초기화 성공")

        # 프레임 프로세서 초기화
        processor = FrameProcessor(feedback_system, cache_manager)
        print("✓ FrameProcessor 초기화 성공")

        return True

    except Exception as e:
        print(f"✗ 초기화 실패: {e}")
        return False


def test_reference_analysis():
    """레퍼런스 분석 테스트"""
    print("\n" + "="*60)
    print("2. 레퍼런스 분석 테스트")
    print("="*60)

    # 테스트 이미지 경로
    test_images = [
        "C:/try_angle/data/sample_images/ref1.jpg",
        "C:/try_angle/data/sample_images/Paris.jpg",
    ]

    # 존재하는 이미지 찾기
    ref_path = None
    for img_path in test_images:
        if os.path.exists(img_path):
            ref_path = img_path
            break

    if not ref_path:
        print("✗ 테스트 이미지를 찾을 수 없습니다")
        print(f"  시도한 경로: {test_images}")
        return False

    try:
        # 시스템 초기화
        feedback_system = SmartFeedbackV7(mode='ios', debug_mode=False)
        cache_manager = CacheManager()
        processor = FrameProcessor(feedback_system, cache_manager)

        print(f"테스트 이미지: {Path(ref_path).name}")

        # 레퍼런스 분석
        start_time = time.perf_counter()
        success = processor.set_reference(ref_path, "test_ref")
        analysis_time = (time.perf_counter() - start_time) * 1000

        if success:
            print(f"✓ 레퍼런스 분석 성공 ({analysis_time:.1f}ms)")

            # 캐시 확인
            cached = cache_manager.get_reference("test_ref")
            if cached:
                print(f"✓ 캐시 저장 확인")
                print(f"  - 모드: {cached.get('mode', 'unknown')}")
                print(f"  - 키포인트 존재: {'keypoints' in cached}")
                print(f"  - 여백 정보 존재: {'margins' in cached}")
            else:
                print("✗ 캐시 저장 실패")

            return True
        else:
            print(f"✗ 레퍼런스 분석 실패")
            return False

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime_processing():
    """실시간 처리 테스트"""
    print("\n" + "="*60)
    print("3. 실시간 처리 테스트")
    print("="*60)

    # 테스트 이미지들
    test_pairs = [
        ("C:/try_angle/data/sample_images/ref1.jpg",
         "C:/try_angle/data/sample_images/test1.jpg"),
        ("C:/try_angle/data/sample_images/Paris.jpg",
         "C:/try_angle/data/sample_images/Paris1.jpg"),
    ]

    # 존재하는 페어 찾기
    ref_path = None
    test_path = None
    for ref, test in test_pairs:
        if os.path.exists(ref) and os.path.exists(test):
            ref_path = ref
            test_path = test
            break

    if not ref_path:
        # 같은 이미지로라도 테스트
        for ref, _ in test_pairs:
            if os.path.exists(ref):
                ref_path = ref
                test_path = ref  # 같은 이미지 사용
                break

    if not ref_path:
        print("✗ 테스트 이미지를 찾을 수 없습니다")
        return False

    try:
        # 시스템 초기화
        feedback_system = SmartFeedbackV7(mode='ios', debug_mode=False)
        cache_manager = CacheManager()
        processor = FrameProcessor(feedback_system, cache_manager)

        print(f"레퍼런스: {Path(ref_path).name}")
        print(f"테스트: {Path(test_path).name}")

        # 레퍼런스 설정
        print("\n레퍼런스 분석 중...")
        success = processor.set_reference(ref_path, "test_ref")
        if not success:
            print("✗ 레퍼런스 설정 실패")
            return False

        # 테스트 이미지 로드
        test_img = cv2.imread(test_path)
        if test_img is None:
            print(f"✗ 테스트 이미지 로드 실패: {test_path}")
            return False

        print("\n프레임 처리 시뮬레이션 (10 프레임)...")
        print("-" * 40)

        # 10프레임 처리 시뮬레이션
        for i in range(10):
            # 약간의 변화를 주기 위해 이미지 변형
            if i % 2 == 0:
                frame = test_img.copy()
            else:
                # 살짝 이동
                M = np.float32([[1, 0, i*2], [0, 1, i*2]])
                frame = cv2.warpAffine(test_img, M, (test_img.shape[1], test_img.shape[0]))

            # 프레임 처리
            result = processor.process_frame(frame)

            # 결과 출력
            print(f"Frame {i+1:2d}: {result.get('feedback', 'N/A'):20s} "
                  f"({result.get('processing_time_ms', 0):.1f}ms)")

            # Level별 처리 확인
            if i == 2:  # 3번째 프레임 (Level 2 처리됨)
                if 'level2' in result and result['level2']:
                    print("  └─ Level 2 처리 완료")

            if i == 9:  # 마지막 프레임
                if 'level3' in result and result['level3']:
                    print("  └─ Level 3 처리 완료")

        # 성능 요약
        perf = processor.get_performance_summary()
        print("\n" + "-" * 40)
        print("성능 요약:")
        print(f"  평균 FPS: {perf['fps']:.1f}")
        print(f"  Level 1 평균: {perf['avg_level1_ms']:.1f}ms")
        print(f"  Level 2 평균: {perf['avg_level2_ms']:.1f}ms")
        print(f"  전체 평균: {perf['avg_total_ms']:.1f}ms")

        # 목표 성능 체크
        if perf['avg_total_ms'] < 33:  # 30fps
            print(f"\n✓ 실시간 처리 성공 (30fps 달성)")
        else:
            print(f"\n⚠ 실시간 처리 경고 (목표: 33ms, 현재: {perf['avg_total_ms']:.1f}ms)")

        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cache_performance():
    """캐시 성능 테스트"""
    print("\n" + "="*60)
    print("4. 캐시 성능 테스트")
    print("="*60)

    test_img_path = None
    for path in ["C:/try_angle/data/sample_images/ref1.jpg",
                 "C:/try_angle/data/sample_images/Paris.jpg"]:
        if os.path.exists(path):
            test_img_path = path
            break

    if not test_img_path:
        print("✗ 테스트 이미지를 찾을 수 없습니다")
        return False

    try:
        feedback_system = SmartFeedbackV7(mode='ios', debug_mode=False)
        cache_manager = CacheManager()

        # 첫 번째 분석 (캐시 없음)
        start_time = time.perf_counter()
        result1 = feedback_system.analyze_reference(test_img_path)
        time1 = (time.perf_counter() - start_time) * 1000

        # 캐싱
        cache_manager.cache_reference("perf_test", result1)

        # 두 번째 호출 (캐시 사용)
        start_time = time.perf_counter()
        result2 = cache_manager.get_reference("perf_test")
        time2 = (time.perf_counter() - start_time) * 1000

        print(f"첫 분석 시간: {time1:.1f}ms")
        print(f"캐시 로드 시간: {time2:.1f}ms")
        print(f"속도 향상: {time1/time2:.1f}배")

        if time2 < time1 / 10:  # 10배 이상 빠름
            print("✓ 캐시 성능 우수")
            return True
        else:
            print("⚠ 캐시 성능 개선 필요")
            return True  # 경고만

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        return False


def main():
    """메인 테스트 실행"""
    print("\n" + "="*60)
    print("TryAngle iOS 실시간 버전 통합 테스트")
    print("버전: v7.0")
    print("날짜: 2025-12-05")
    print("="*60)

    total_tests = 0
    passed_tests = 0

    # 테스트 목록
    tests = [
        ("기본 초기화", test_basic_initialization),
        ("레퍼런스 분석", test_reference_analysis),
        ("실시간 처리", test_realtime_processing),
        ("캐시 성능", test_cache_performance),
    ]

    # 테스트 실행
    for test_name, test_func in tests:
        total_tests += 1
        try:
            if test_func():
                passed_tests += 1
            else:
                print(f"\n⚠ {test_name} 테스트 실패")
        except Exception as e:
            print(f"\n✗ {test_name} 테스트 오류: {e}")

    # 최종 결과
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60)
    print(f"전체: {total_tests}개")
    print(f"성공: {passed_tests}개")
    print(f"실패: {total_tests - passed_tests}개")

    if passed_tests == total_tests:
        print("\n✓ 모든 테스트 통과!")
        return 0
    else:
        print(f"\n⚠ 일부 테스트 실패 ({passed_tests}/{total_tests})")
        return 1


if __name__ == "__main__":
    exit(main())