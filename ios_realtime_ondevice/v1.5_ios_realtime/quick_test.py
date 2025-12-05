"""
빠른 API 테스트 스크립트
작성일: 2025-12-05
"""

import requests
import json
import os
import time

# 서버 URL
SERVER_URL = "http://localhost:8000"

# 테스트 이미지 경로
TEST_IMAGES = r"C:\try_angle\data\sample_images"

def test_server_status():
    """서버 상태 확인"""
    print("\n1. 서버 상태 확인...")
    try:
        response = requests.get(f"{SERVER_URL}/", timeout=2)
        if response.status_code == 200:
            print("✅ 서버 실행 중!")
            print(f"   응답: {response.json()}")
            return True
        else:
            print("❌ 서버 응답 오류")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 서버가 실행되지 않았습니다!")
        print("   다음 명령어로 서버를 먼저 실행하세요:")
        print('   python api_server.py')
        return False

def test_reference_analysis():
    """레퍼런스 분석 테스트"""
    print("\n2. 레퍼런스 이미지 분석...")

    ref_image = os.path.join(TEST_IMAGES, "ref1.jpg")
    if not os.path.exists(ref_image):
        print(f"❌ 이미지 없음: {ref_image}")
        return None

    with open(ref_image, "rb") as f:
        files = {"image": f}
        response = requests.post(f"{SERVER_URL}/analyze_reference", files=files)

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 레퍼런스 분석 완료!")
        print(f"   Reference ID: {result.get('reference_id', 'N/A')}")
        if result.get('analysis'):
            analysis = result['analysis']
            if analysis.get('has_person'):
                print(f"   - 사람 검출: O")
                print(f"   - 구도: {analysis.get('composition_type', 'unknown')}")
        return result.get('reference_id')
    else:
        print("❌ 레퍼런스 분석 실패")
        return None

def test_frame_processing(ref_id=None):
    """프레임 처리 테스트"""
    print("\n3. 프레임 처리 테스트...")

    test_image = os.path.join(TEST_IMAGES, "mz1.jpg")
    if not os.path.exists(test_image):
        print(f"❌ 이미지 없음: {test_image}")
        return

    # 동기 처리 테스트 (더 안정적)
    with open(test_image, "rb") as f:
        files = {"image": f}
        data = {"ref_id": ref_id} if ref_id else {}

        start_time = time.time()
        response = requests.post(f"{SERVER_URL}/process_frame_sync", files=files, data=data)
        process_time = (time.time() - start_time) * 1000

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 프레임 처리 완료! (처리시간: {process_time:.1f}ms)")

        # 피드백 출력
        feedback = result.get('feedback', {})
        if feedback.get('primary'):
            print(f"\n   📝 주요 피드백: {feedback['primary']}")

        if feedback.get('suggestions'):
            print("   💡 제안사항:")
            for sug in feedback['suggestions'][:3]:
                print(f"      - {sug}")

        # Depth 정보
        if result.get('depth_info'):
            depth = result['depth_info']
            print(f"\n   📷 카메라 정보:")
            print(f"      - 압축감: {depth.get('compression_index', 0):.2f}")
            print(f"      - 타입: {depth.get('camera_type', 'unknown')}")
    else:
        print("❌ 프레임 처리 실패")
        print(f"   응답: {response.text}")

def test_performance():
    """성능 테스트 (연속 처리)"""
    print("\n4. 성능 테스트 (5프레임 연속)...")

    test_image = os.path.join(TEST_IMAGES, "mz1.jpg")
    if not os.path.exists(test_image):
        return

    times = []
    for i in range(5):
        with open(test_image, "rb") as f:
            files = {"image": f}
            start = time.time()
            response = requests.post(f"{SERVER_URL}/process_frame", files=files)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

            if response.status_code == 200:
                print(f"   프레임 {i+1}: {elapsed:.1f}ms")
            else:
                print(f"   프레임 {i+1}: 실패")

    if times:
        avg_time = sum(times) / len(times)
        print(f"\n   📊 평균 처리시간: {avg_time:.1f}ms")
        print(f"   📊 예상 FPS: {1000/avg_time:.1f}")

def test_stats():
    """통계 확인"""
    print("\n5. 서버 통계...")
    response = requests.get(f"{SERVER_URL}/stats")
    if response.status_code == 200:
        stats = response.json()
        print("✅ 통계 조회 성공!")

        if stats.get('async_processor'):
            ap = stats['async_processor']
            print(f"   - 처리된 프레임: {ap.get('processed_frames', 0)}")
            print(f"   - 스킵된 프레임: {ap.get('skipped_frames', 0)}")
            print(f"   - 평균 처리시간: {ap.get('avg_process_time_ms', 0):.1f}ms")

def main():
    """메인 테스트"""
    print("="*60)
    print("TryAngle iOS API 빠른 테스트")
    print("="*60)

    # 1. 서버 확인
    if not test_server_status():
        return

    # 2. 레퍼런스 분석
    ref_id = test_reference_analysis()

    # 3. 프레임 처리
    test_frame_processing(ref_id)

    # 4. 성능 테스트
    test_performance()

    # 5. 통계
    test_stats()

    print("\n" + "="*60)
    print("테스트 완료!")
    print("\n💡 웹 UI로도 테스트 가능: http://localhost:8000/test")
    print("="*60)

if __name__ == "__main__":
    main()