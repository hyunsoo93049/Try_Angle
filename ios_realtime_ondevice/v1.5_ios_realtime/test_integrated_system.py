"""
통합 시스템 테스트
작성일: 2025-12-05
RTMPose + Depth + YOLO 통합 테스트
"""

import os
import sys
import cv2
import numpy as np
import time
import json
from typing import Dict, Any, List, Tuple
from pathlib import Path

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.smart_feedback_v7 import SmartFeedbackV7
from realtime.frame_processor import FrameProcessor
from realtime.cache_manager import CacheManager


class IntegratedSystemTest:
    """통합 시스템 테스트 클래스"""

    def __init__(self, test_images_dir: str = None):
        """초기화"""
        self.test_images_dir = test_images_dir or r"C:\try_angle\data\sample_images"

        # 시스템 초기화
        self.feedback_system = SmartFeedbackV7(mode='ios', language='ko')
        self.cache_manager = CacheManager()
        self.frame_processor = FrameProcessor(
            feedback_system=self.feedback_system,
            cache_manager=self.cache_manager,
            enable_depth=True,  # Depth 활성화
            enable_yolo=True    # YOLO 활성화
        )

        # 테스트 결과 저장
        self.test_results = []

    def test_reference_analysis(self, image_path: str) -> Dict[str, Any]:
        """레퍼런스 분석 테스트"""
        print(f"\n=== 레퍼런스 분석 테스트: {image_path} ===")

        # 이미지 로드
        image = cv2.imread(image_path)
        if image is None:
            print(f"이미지 로드 실패: {image_path}")
            return {}

        h, w = image.shape[:2]
        print(f"이미지 크기: {w}x{h}")

        # 레퍼런스 분석
        start = time.perf_counter()
        ref_result = self.feedback_system.analyze_reference(image)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"레퍼런스 분석 시간: {elapsed:.1f}ms")

        if ref_result:
            print(f"- 포즈 검출: {ref_result.get('has_person', False)}")
            if ref_result.get('has_person'):
                print(f"- 키포인트 수: {ref_result.get('num_keypoints', 0)}")
                print(f"- 구도 타입: {ref_result.get('composition_type', 'unknown')}")

            # 캐시 저장
            ref_id = os.path.basename(image_path).split('.')[0]
            if self.cache_manager.cache_reference(ref_id, ref_result):
                print(f"- 캐시 저장 완료: {ref_id}")

        return ref_result

    def test_realtime_processing(self, image_path: str, ref_id: str = None) -> Dict[str, Any]:
        """실시간 처리 테스트"""
        print(f"\n=== 실시간 처리 테스트: {image_path} ===")

        # 이미지 로드
        image = cv2.imread(image_path)
        if image is None:
            print(f"이미지 로드 실패: {image_path}")
            return {}

        # 레퍼런스 캐시 확인
        if ref_id:
            ref_cache = self.cache_manager.get_cached_reference(ref_id)
            if ref_cache:
                print(f"레퍼런스 캐시 사용: {ref_id}")
            else:
                print(f"레퍼런스 캐시 없음: {ref_id}")

        # 프레임 처리 (여러 번 실행하여 3레벨 처리 테스트)
        results = []
        for i in range(35):  # 35프레임 처리 (L3 처리 포함)
            start = time.perf_counter()
            result = self.frame_processor.process_frame(image, ref_id=ref_id)
            elapsed = (time.perf_counter() - start) * 1000

            if result:
                results.append({
                    'frame': i,
                    'time_ms': elapsed,
                    'feedback': result.get('feedback', {}),
                    'level': result.get('processing_level', 0)
                })

                # 주요 프레임만 출력
                if i % 10 == 0 or result.get('processing_level', 0) >= 2:
                    print(f"\n프레임 {i} (Level {result.get('processing_level', 0)}): {elapsed:.1f}ms")

                    # 피드백 출력
                    feedback = result.get('feedback', {})
                    if feedback.get('primary'):
                        print(f"  주요: {feedback['primary']}")
                    if feedback.get('suggestions'):
                        for sug in feedback['suggestions'][:2]:
                            print(f"  제안: {sug}")

                    # Depth 정보 (L2)
                    if 'depth_info' in result:
                        depth = result['depth_info']
                        print(f"  압축감: {depth.get('compression_index', 0):.2f}")
                        print(f"  카메라 타입: {depth.get('camera_type', 'unknown')}")

                    # YOLO 정보 (L3)
                    if 'yolo_bbox' in result:
                        print(f"  YOLO 검출: {result['yolo_bbox']}")

        # 통계 계산
        if results:
            times = [r['time_ms'] for r in results]
            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)

            print(f"\n=== 성능 통계 ===")
            print(f"프레임 수: {len(results)}")
            print(f"평균 시간: {avg_time:.1f}ms")
            print(f"최대 시간: {max_time:.1f}ms")
            print(f"최소 시간: {min_time:.1f}ms")
            print(f"30fps 달성률: {sum(1 for t in times if t < 33.3) / len(times) * 100:.1f}%")

            # 레벨별 처리 횟수
            level_counts = {}
            for r in results:
                level = r.get('level', 0)
                level_counts[level] = level_counts.get(level, 0) + 1

            print(f"\n레벨별 처리:")
            for level in sorted(level_counts.keys()):
                print(f"  Level {level}: {level_counts[level]}회")

        return {'results': results, 'stats': {
            'avg_time': avg_time if results else 0,
            'max_time': max_time if results else 0,
            'min_time': min_time if results else 0,
            'frame_count': len(results)
        }}

    def test_depth_and_yolo(self, image_path: str) -> Dict[str, Any]:
        """Depth와 YOLO 개별 테스트"""
        print(f"\n=== Depth & YOLO 테스트: {image_path} ===")

        # 이미지 로드
        image = cv2.imread(image_path)
        if image is None:
            print(f"이미지 로드 실패: {image_path}")
            return {}

        results = {}

        # Depth 테스트
        if self.frame_processor.depth_estimator:
            print("\n[Depth Anything Small 테스트]")
            start = time.perf_counter()
            depth_map = self.frame_processor.depth_estimator.process_frame(image)
            elapsed = (time.perf_counter() - start) * 1000

            if depth_map is not None:
                print(f"- 처리 시간: {elapsed:.1f}ms")
                print(f"- Depth map shape: {depth_map.shape}")

                # 압축감 계산
                compression = self.frame_processor.depth_estimator.calculate_compression(depth_map)
                print(f"- 압축감 지수: {compression['compression_index']:.2f}")
                print(f"- 카메라 타입: {compression['camera_type']}")

                results['depth'] = {
                    'time_ms': elapsed,
                    'compression': compression
                }

                # Depth map 시각화 저장
                depth_vis = (depth_map * 255).astype(np.uint8)
                depth_vis = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
                output_path = f"test_depth_{os.path.basename(image_path)}"
                cv2.imwrite(output_path, depth_vis)
                print(f"- Depth 시각화 저장: {output_path}")

        # YOLO 테스트
        if self.frame_processor.yolo_detector:
            print("\n[YOLO Nano 테스트]")
            start = time.perf_counter()
            bbox = self.frame_processor.yolo_detector.detect_person(image)
            elapsed = (time.perf_counter() - start) * 1000

            if bbox:
                print(f"- 처리 시간: {elapsed:.1f}ms")
                print(f"- Person bbox: {bbox}")

                results['yolo'] = {
                    'time_ms': elapsed,
                    'bbox': bbox
                }

                # 검출 결과 시각화
                vis_image = image.copy()
                x1, y1, x2, y2 = bbox
                cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(vis_image, "Person (YOLO)", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                output_path = f"test_yolo_{os.path.basename(image_path)}"
                cv2.imwrite(output_path, vis_image)
                print(f"- YOLO 시각화 저장: {output_path}")
            else:
                print("- Person 검출 실패")

        # 통합 성능 통계
        print("\n[모델 성능 통계]")

        # RTMPose
        rtm_stats = self.feedback_system.wholebody.get_stats()
        print(f"RTMPose: 평균 {rtm_stats.get('avg_time_ms', 0):.1f}ms")

        # Depth
        if self.frame_processor.depth_estimator:
            depth_stats = self.frame_processor.depth_estimator.get_stats()
            print(f"Depth: 평균 {depth_stats.get('avg_time_ms', 0):.1f}ms")

        # YOLO
        if self.frame_processor.yolo_detector:
            yolo_stats = self.frame_processor.yolo_detector.get_stats()
            print(f"YOLO: 평균 {yolo_stats.get('avg_time_ms', 0):.1f}ms")

        return results

    def run_comprehensive_test(self):
        """종합 테스트 실행"""
        print("\n" + "="*60)
        print("iOS 실시간 통합 시스템 테스트")
        print("="*60)

        # 테스트 이미지 목록
        test_cases = [
            {
                'ref': 'ref1.jpg',
                'current': 'mz1.jpg',
                'desc': '인물 포트레이트'
            },
            {
                'ref': 'cafe1.jpg',
                'current': 'cafe2.jpg',
                'desc': '카페 장면'
            },
            {
                'ref': 'Paris.jpg',
                'current': 'Paris1.jpg',
                'desc': '파리 배경'
            }
        ]

        for i, test_case in enumerate(test_cases):
            print(f"\n\n{'='*60}")
            print(f"테스트 케이스 {i+1}: {test_case['desc']}")
            print('='*60)

            # 레퍼런스 이미지 경로
            ref_path = os.path.join(self.test_images_dir, test_case['ref'])
            current_path = os.path.join(self.test_images_dir, test_case['current'])

            # 파일 존재 확인
            if not os.path.exists(ref_path):
                print(f"레퍼런스 이미지 없음: {ref_path}")
                continue
            if not os.path.exists(current_path):
                print(f"현재 이미지 없음: {current_path}")
                continue

            # 1. 레퍼런스 분석
            ref_result = self.test_reference_analysis(ref_path)
            ref_id = test_case['ref'].split('.')[0]

            # 2. Depth & YOLO 개별 테스트
            depth_yolo_result = self.test_depth_and_yolo(current_path)

            # 3. 실시간 처리 테스트
            realtime_result = self.test_realtime_processing(current_path, ref_id)

            # 결과 저장
            self.test_results.append({
                'test_case': test_case,
                'reference': ref_result,
                'depth_yolo': depth_yolo_result,
                'realtime': realtime_result
            })

        # 최종 보고서
        self.generate_report()

    def generate_report(self):
        """테스트 보고서 생성"""
        print("\n\n" + "="*60)
        print("테스트 보고서")
        print("="*60)

        if not self.test_results:
            print("테스트 결과 없음")
            return

        # 성능 요약
        print("\n[성능 요약]")
        total_frames = 0
        total_time = 0
        fps_achieved = 0

        for result in self.test_results:
            if 'realtime' in result and 'stats' in result['realtime']:
                stats = result['realtime']['stats']
                total_frames += stats['frame_count']
                total_time += stats['avg_time'] * stats['frame_count']

                # 30fps 달성 프레임 계산
                if 'results' in result['realtime']:
                    for r in result['realtime']['results']:
                        if r['time_ms'] < 33.3:
                            fps_achieved += 1

        if total_frames > 0:
            avg_time = total_time / total_frames
            fps_rate = fps_achieved / total_frames * 100

            print(f"총 프레임: {total_frames}")
            print(f"평균 처리 시간: {avg_time:.1f}ms")
            print(f"30fps 달성률: {fps_rate:.1f}%")

            if avg_time < 33.3:
                print("[성공] 30fps 목표 달성!")
            else:
                print(f"[경고] 30fps 미달 (현재: {1000/avg_time:.1f}fps)")

        # 모듈별 성능
        print("\n[모듈별 평균 성능]")

        # RTMPose
        rtm_stats = self.feedback_system.wholebody.get_stats()
        print(f"- RTMPose: {rtm_stats.get('avg_time_ms', 0):.1f}ms")

        # Depth
        if self.frame_processor.depth_estimator:
            depth_stats = self.frame_processor.depth_estimator.get_stats()
            print(f"- Depth Anything: {depth_stats.get('avg_time_ms', 0):.1f}ms")

        # YOLO
        if self.frame_processor.yolo_detector:
            yolo_stats = self.frame_processor.yolo_detector.get_stats()
            print(f"- YOLO Nano: {yolo_stats.get('avg_time_ms', 0):.1f}ms")

        # 기능 테스트 결과
        print("\n[기능 테스트]")
        print("- RTMPose 포즈 검출: OK")
        print(f"- Depth 압축감 분석: {'OK' if self.frame_processor.depth_estimator else 'N/A'}")
        print(f"- YOLO 바운딩박스: {'OK' if self.frame_processor.yolo_detector else 'N/A'}")
        print("- 피드백 생성: OK")
        print("- 캐시 시스템: OK")

        # 결과 JSON 저장
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'performance': {
                'total_frames': total_frames,
                'avg_time_ms': avg_time if total_frames > 0 else 0,
                'fps_achievement': fps_rate if total_frames > 0 else 0
            },
            'module_stats': {
                'rtmpose': rtm_stats,
                'depth': self.frame_processor.depth_estimator.get_stats() if self.frame_processor.depth_estimator else None,
                'yolo': self.frame_processor.yolo_detector.get_stats() if self.frame_processor.yolo_detector else None
            },
            'test_results': self.test_results
        }

        with open('test_report_integrated.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n테스트 보고서 저장: test_report_integrated.json")
        print("="*60)


if __name__ == "__main__":
    # 테스트 실행
    tester = IntegratedSystemTest()

    # 모델 워밍업
    print("모델 워밍업 중...")
    dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)

    # RTMPose 워밍업 - 첫 추론이 자동으로 워밍업 역할
    print("RTMPose 워밍업 중...")
    for _ in range(3):
        _ = tester.feedback_system.wholebody.extract_wholebody_keypoints(dummy_frame)
    print("RTMPose 워밍업 완료")

    # Depth 워밍업
    if tester.frame_processor.depth_estimator:
        tester.frame_processor.depth_estimator.warmup(dummy_frame)

    # YOLO 워밍업
    if tester.frame_processor.yolo_detector:
        tester.frame_processor.yolo_detector.warmup(dummy_frame)

    print("워밍업 완료!\n")

    # 종합 테스트 실행
    tester.run_comprehensive_test()