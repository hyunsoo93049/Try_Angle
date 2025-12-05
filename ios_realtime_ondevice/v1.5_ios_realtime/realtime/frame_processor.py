"""
실시간 프레임 처리 모듈
작성일: 2025-12-05

프레임별 처리 로직 및 레벨별 분석 관리
"""

import time
import numpy as np
from typing import Dict, Optional, Any, Tuple
from collections import deque
import threading
from queue import Queue
import sys
from pathlib import Path

# 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

# 모델 임포트
from models.depth_small_wrapper import DepthAnythingSmall
from models.yolo_nano_wrapper import YOLONano


class FrameProcessor:
    """
    실시간 프레임 처리기

    3단계 처리 레벨:
    - Level 1: 매 프레임 (RTMPose)
    - Level 2: 3프레임마다 (Depth)
    - Level 3: 30프레임마다 (추가 분석)
    """

    def __init__(self, feedback_system=None, cache_manager=None, enable_depth=True, enable_yolo=False):
        """
        초기화
        Args:
            feedback_system: SmartFeedbackV7 인스턴스
            cache_manager: CacheManager 인스턴스
            enable_depth: Depth 분석 활성화
            enable_yolo: YOLO 검출 활성화
        """
        self.feedback_system = feedback_system
        self.cache_manager = cache_manager

        # 모델 초기화
        self.depth_estimator = DepthAnythingSmall(device='cpu') if enable_depth else None
        self.yolo_detector = YOLONano(device='cpu') if enable_yolo else None

        # 프레임 카운터
        self.frame_count = 0
        self.start_time = time.time()

        # 레벨별 처리 간격
        self.intervals = {
            'level1': 1,   # 매 프레임
            'level2': 3,   # 3프레임마다
            'level3': 30   # 30프레임마다 (1초)
        }

        # 성능 모니터링
        self.performance_stats = {
            'level1_times': deque(maxlen=100),
            'level2_times': deque(maxlen=100),
            'level3_times': deque(maxlen=100),
            'total_times': deque(maxlen=100),
            'fps': 0
        }

        # 비동기 처리용 큐
        self.processing_queue = Queue()
        self.result_queue = Queue()

        # 마지막 결과 캐시
        self.last_results = {
            'level1': None,
            'level2': None,
            'level3': None,
            'feedback': None
        }

        # 레퍼런스 데이터
        self.reference_cache = None
        self.reference_id = None

    def set_reference(self, reference_path: str, reference_id: Optional[str] = None) -> bool:
        """
        레퍼런스 설정

        Args:
            reference_path: 레퍼런스 이미지 경로
            reference_id: 레퍼런스 ID (캐시 키)

        Returns:
            성공 여부
        """
        try:
            if not reference_id:
                reference_id = str(hash(reference_path))

            # 캐시 확인
            if self.cache_manager:
                cached = self.cache_manager.get_reference(reference_id)
                if cached:
                    self.reference_cache = cached
                    self.reference_id = reference_id
                    print(f"[FrameProcessor] 캐시된 레퍼런스 사용: {reference_id}")
                    return True

            # 새로 분석
            if self.feedback_system:
                print(f"[FrameProcessor] 레퍼런스 분석 중...")
                analysis = self.feedback_system.analyze_reference(reference_path)

                if 'error' not in analysis:
                    self.reference_cache = analysis
                    self.reference_id = reference_id

                    # 캐싱
                    if self.cache_manager:
                        self.cache_manager.cache_reference(reference_id, analysis)

                    print(f"[FrameProcessor] 레퍼런스 분석 완료")
                    return True
                else:
                    print(f"[FrameProcessor] 레퍼런스 분석 실패: {analysis['error']}")
                    return False
            else:
                print("[FrameProcessor] Feedback system이 설정되지 않음")
                return False

        except Exception as e:
            print(f"[FrameProcessor] 레퍼런스 설정 실패: {e}")
            return False

    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        프레임 처리 (메인 메서드)

        Args:
            frame: 입력 프레임 (numpy array)

        Returns:
            처리 결과 딕셔너리
        """
        if not self.reference_cache:
            return {'error': '레퍼런스가 설정되지 않음'}

        self.frame_count += 1
        start_time = time.perf_counter()

        result = {
            'frame_number': self.frame_count,
            'timestamp': time.time()
        }

        # Level 1: 매 프레임 처리
        level1_start = time.perf_counter()
        level1_result = self._process_level1(frame)
        level1_time = (time.perf_counter() - level1_start) * 1000
        self.performance_stats['level1_times'].append(level1_time)
        result['level1'] = level1_result
        self.last_results['level1'] = level1_result

        # Level 2: 3프레임마다
        if self.frame_count % self.intervals['level2'] == 0:
            level2_start = time.perf_counter()
            level2_result = self._process_level2(frame, level1_result)
            level2_time = (time.perf_counter() - level2_start) * 1000
            self.performance_stats['level2_times'].append(level2_time)
            result['level2'] = level2_result
            self.last_results['level2'] = level2_result
        else:
            result['level2'] = self.last_results.get('level2')

        # Level 3: 30프레임마다
        if self.frame_count % self.intervals['level3'] == 0:
            level3_start = time.perf_counter()
            level3_result = self._process_level3(frame, level1_result)
            level3_time = (time.perf_counter() - level3_start) * 1000
            self.performance_stats['level3_times'].append(level3_time)
            result['level3'] = level3_result
            self.last_results['level3'] = level3_result
        else:
            result['level3'] = self.last_results.get('level3')

        # 피드백 생성
        feedback = self._generate_combined_feedback(
            level1_result,
            self.last_results.get('level2'),
            self.last_results.get('level3')
        )
        result['feedback'] = feedback
        self.last_results['feedback'] = feedback

        # 전체 처리 시간
        total_time = (time.perf_counter() - start_time) * 1000
        self.performance_stats['total_times'].append(total_time)
        result['processing_time_ms'] = total_time

        # FPS 계산
        if self.frame_count > 0:
            elapsed = time.time() - self.start_time
            self.performance_stats['fps'] = self.frame_count / elapsed

        result['performance'] = self.get_performance_summary()

        return result

    def _process_level1(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Level 1: 매 프레임 처리
        RTMPose 키포인트 추출 및 빠른 여백 계산
        """
        try:
            if self.feedback_system:
                # RTMPose 키포인트 추출
                keypoints = self.feedback_system.wholebody.extract_wholebody_keypoints(frame)

                # 빠른 여백 계산
                margin_result = self.feedback_system.margin_analyzer.analyze_margins_unified(
                    keypoints,
                    self.reference_cache['keypoints'],
                    frame.shape,
                    self.reference_cache['image_shape']
                )

                # 보정 계수 적용 (있는 경우)
                if self.cache_manager and self.reference_id:
                    calibrated_margins = self.cache_manager.apply_calibration(
                        margin_result['current_margins'],
                        self.reference_id
                    )
                    margin_result['calibrated_margins'] = calibrated_margins

                return {
                    'keypoints': keypoints,
                    'margins': margin_result,
                    'status': 'success'
                }
            else:
                return {'status': 'no_feedback_system'}

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _process_level2(self, frame: np.ndarray, level1_result: Dict) -> Dict[str, Any]:
        """
        Level 2: 3프레임마다 처리
        Depth 분석 + 프레이밍 분석
        """
        try:
            result = {}

            # 프레이밍 분석
            if self.feedback_system and level1_result.get('keypoints'):
                framing_result = self.feedback_system.framing_analyzer.analyze(
                    level1_result['keypoints'],
                    frame.shape
                )
                result['framing'] = framing_result

            # Depth 분석
            if self.depth_estimator:
                depth_map = self.depth_estimator.process_frame(frame)
                if depth_map is not None:
                    # 인물 bbox (RTMPose 키포인트에서 계산)
                    person_bbox = self._get_bbox_from_keypoints(level1_result.get('keypoints'))

                    # 압축감 계산
                    compression = self.depth_estimator.calculate_compression(depth_map, person_bbox)
                    result['depth'] = {
                        'map': depth_map,
                        'compression': compression
                    }
                else:
                    result['depth'] = None
            else:
                result['depth'] = None

            result['status'] = 'success'
            return result

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _process_level3(self, frame: np.ndarray, level1_result: Dict) -> Dict[str, Any]:
        """
        Level 3: 30프레임마다 처리
        YOLO 검출 + 통계 수집
        """
        try:
            result = {}

            # YOLO 인물 검출 (bbox 보정용)
            if self.yolo_detector:
                yolo_bbox = self.yolo_detector.detect_person(frame)
                if yolo_bbox:
                    # RTMPose bbox와 비교하여 보정 계수 계산
                    rtm_bbox = self._get_bbox_from_keypoints(level1_result.get('keypoints'))
                    if rtm_bbox:
                        calibration = self._calculate_bbox_calibration(rtm_bbox, yolo_bbox)
                        result['yolo_bbox'] = yolo_bbox
                        result['calibration'] = calibration

            # 통계 수집
            stats = {
                'avg_processing_time': np.mean(self.performance_stats['total_times']) if self.performance_stats['total_times'] else 0,
                'fps': self.performance_stats['fps'],
                'frame_count': self.frame_count
            }
            result.update(stats)
            result['status'] = 'success'

            return result

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _generate_combined_feedback(self, level1: Optional[Dict],
                                   level2: Optional[Dict],
                                   level3: Optional[Dict]) -> str:
        """
        통합 피드백 생성 (개선된 버전)
        """
        feedbacks = []
        priority_score = {}

        # Level 1 피드백 (여백) - 우선순위 높음
        if level1 and 'margins' in level1:
            margin_feedback = level1['margins'].get('actionable_feedback', {})

            # 수평 피드백
            if margin_feedback.get('horizontal'):
                h_text = margin_feedback['horizontal']
                if '왼쪽' in h_text:
                    priority_score["← 왼쪽"] = 3
                elif '오른쪽' in h_text:
                    priority_score["→ 오른쪽"] = 3

            # 수직 피드백
            if margin_feedback.get('vertical'):
                v_text = margin_feedback['vertical']
                if '위' in v_text or '올려' in v_text:
                    priority_score["↑ 위로"] = 3
                elif '아래' in v_text or '내려' in v_text:
                    priority_score["↓ 아래로"] = 3

        # Level 2 피드백 (프레이밍 + 깊이)
        if level2:
            # 프레이밍
            if 'framing' in level2:
                framing = level2['framing']
                if framing and 'subject_ratio' in framing:
                    ratio = framing['subject_ratio']
                    if ratio < 0.25:
                        priority_score["가까이"] = 2
                    elif ratio > 0.65:
                        priority_score["멀리"] = 2

            # 깊이/압축감
            if 'depth' in level2 and level2['depth']:
                compression = level2['depth'].get('compression', {})
                camera_type = compression.get('camera_type', '')

                # 레퍼런스와 비교하여 피드백 (나중에 구현)
                if camera_type == 'wide' and self.reference_cache:
                    ref_compression = self.reference_cache.get('compression', {})
                    if ref_compression.get('camera_type') == 'telephoto':
                        priority_score["줌인"] = 1
                elif camera_type == 'telephoto' and self.reference_cache:
                    ref_compression = self.reference_cache.get('compression', {})
                    if ref_compression.get('camera_type') == 'wide':
                        priority_score["줌아웃"] = 1

        # 우선순위별 정렬
        sorted_feedbacks = sorted(priority_score.items(), key=lambda x: x[1], reverse=True)
        feedbacks = [fb[0] for fb in sorted_feedbacks[:2]]  # 최대 2개

        if feedbacks:
            return " | ".join(feedbacks)
        else:
            return "✓ 좋아요"

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        성능 요약 반환
        """
        return {
            'fps': round(self.performance_stats['fps'], 1),
            'avg_level1_ms': round(np.mean(self.performance_stats['level1_times']), 1) if self.performance_stats['level1_times'] else 0,
            'avg_level2_ms': round(np.mean(self.performance_stats['level2_times']), 1) if self.performance_stats['level2_times'] else 0,
            'avg_level3_ms': round(np.mean(self.performance_stats['level3_times']), 1) if self.performance_stats['level3_times'] else 0,
            'avg_total_ms': round(np.mean(self.performance_stats['total_times']), 1) if self.performance_stats['total_times'] else 0,
            'frame_count': self.frame_count
        }

    def _get_bbox_from_keypoints(self, keypoints: Optional[Dict]) -> Optional[Tuple[int, int, int, int]]:
        """
        키포인트에서 바운딩 박스 계산
        """
        if not keypoints:
            return None

        try:
            all_points = []

            # 모든 키포인트 수집
            for body_part in keypoints.get('body_keypoints', {}).values():
                if 'position' in body_part:
                    all_points.append(body_part['position'])

            if not all_points:
                return None

            points = np.array(all_points)
            x1, y1 = int(points[:, 0].min()), int(points[:, 1].min())
            x2, y2 = int(points[:, 0].max()), int(points[:, 1].max())

            return (x1, y1, x2, y2)

        except Exception:
            return None

    def _calculate_bbox_calibration(self, rtm_bbox: Tuple, yolo_bbox: Tuple) -> Dict[str, float]:
        """
        RTMPose bbox와 YOLO bbox 간의 보정 계수 계산
        """
        try:
            rtm_x1, rtm_y1, rtm_x2, rtm_y2 = rtm_bbox
            yolo_x1, yolo_y1, yolo_x2, yolo_y2 = yolo_bbox

            # 크기 비율
            rtm_width = rtm_x2 - rtm_x1
            rtm_height = rtm_y2 - rtm_y1
            yolo_width = yolo_x2 - yolo_x1
            yolo_height = yolo_y2 - yolo_y1

            calibration = {
                'width_ratio': yolo_width / (rtm_width + 1e-6),
                'height_ratio': yolo_height / (rtm_height + 1e-6),
                'x_offset': (yolo_x1 + yolo_x2) / 2 - (rtm_x1 + rtm_x2) / 2,
                'y_offset': (yolo_y1 + yolo_y2) / 2 - (rtm_y1 + rtm_y2) / 2
            }

            return calibration

        except Exception:
            return {'width_ratio': 1.0, 'height_ratio': 1.0, 'x_offset': 0, 'y_offset': 0}

    def reset(self):
        """
        프로세서 초기화
        """
        self.frame_count = 0
        self.start_time = time.time()
        self.last_results.clear()
        for key in self.performance_stats:
            if isinstance(self.performance_stats[key], deque):
                self.performance_stats[key].clear()
            else:
                self.performance_stats[key] = 0


if __name__ == "__main__":
    # 간단한 테스트
    processor = FrameProcessor()

    # 더미 프레임
    dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    # 10프레임 처리 시뮬레이션
    for i in range(10):
        result = processor.process_frame(dummy_frame)
        print(f"Frame {i+1}: {result.get('feedback', 'N/A')}")

        # 성능 출력
        if i == 9:
            perf = processor.get_performance_summary()
            print(f"\n성능 요약:")
            print(f"  FPS: {perf['fps']}")
            print(f"  평균 처리 시간: {perf['avg_total_ms']}ms")