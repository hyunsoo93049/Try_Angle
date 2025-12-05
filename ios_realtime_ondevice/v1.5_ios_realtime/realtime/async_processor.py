"""
비동기 프레임 처리 시스템
작성일: 2025-12-05
프레임 스킵 및 비동기 처리를 통한 성능 최적화
"""

import asyncio
import threading
import queue
import time
import numpy as np
from typing import Optional, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class FrameTask:
    """프레임 처리 태스크"""
    frame_id: int
    frame: np.ndarray
    timestamp: float
    priority: int = 0  # 0=높음, 1=중간, 2=낮음
    ref_id: Optional[str] = None


@dataclass
class ProcessingResult:
    """처리 결과"""
    frame_id: int
    timestamp: float
    processing_time: float
    result: Dict[str, Any]
    skipped: bool = False


class AsyncFrameProcessor:
    """
    비동기 프레임 처리기

    특징:
    - 프레임 스킵을 통한 30fps 보장
    - 비동기 처리로 UI 블로킹 방지
    - 우선순위 기반 처리
    """

    def __init__(self, frame_processor, max_workers: int = 2):
        """
        초기화

        Args:
            frame_processor: FrameProcessor 인스턴스
            max_workers: 최대 워커 스레드 수
        """
        self.frame_processor = frame_processor
        self.max_workers = max_workers

        # 큐와 스레드풀
        self.task_queue = queue.PriorityQueue(maxsize=10)
        self.result_queue = queue.Queue(maxsize=30)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 상태
        self.is_running = False
        self.frame_counter = 0
        self.last_process_time = 0
        self.skip_threshold = 0.033  # 33ms (30fps)

        # 통계
        self.stats = {
            'total_frames': 0,
            'processed_frames': 0,
            'skipped_frames': 0,
            'avg_process_time': 0,
            'total_process_time': 0
        }

        # 워커 스레드
        self.worker_thread = None

    def start(self):
        """비동기 처리 시작"""
        if self.is_running:
            return

        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        print("[AsyncProcessor] 비동기 처리 시작")

    def stop(self):
        """비동기 처리 중지"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        self.executor.shutdown(wait=False)
        print("[AsyncProcessor] 비동기 처리 중지")

    def submit_frame(self, frame: np.ndarray, ref_id: Optional[str] = None) -> int:
        """
        프레임 제출

        Args:
            frame: 입력 프레임
            ref_id: 레퍼런스 ID

        Returns:
            frame_id: 프레임 ID
        """
        self.frame_counter += 1
        frame_id = self.frame_counter
        timestamp = time.perf_counter()

        # 프레임 스킵 결정
        if self._should_skip_frame(timestamp):
            self.stats['skipped_frames'] += 1
            # 스킵된 프레임 결과 즉시 추가
            result = ProcessingResult(
                frame_id=frame_id,
                timestamp=timestamp,
                processing_time=0,
                result={'skipped': True},
                skipped=True
            )
            self.result_queue.put(result)
            return frame_id

        # 우선순위 결정 (매 30프레임마다 높은 우선순위)
        priority = 0 if frame_id % 30 == 0 else (1 if frame_id % 3 == 0 else 2)

        # 태스크 생성
        task = FrameTask(
            frame_id=frame_id,
            frame=frame.copy(),  # 복사본 사용
            timestamp=timestamp,
            priority=priority,
            ref_id=ref_id
        )

        # 큐에 추가 (블로킹 방지)
        try:
            self.task_queue.put_nowait((priority, frame_id, task))
            self.stats['total_frames'] += 1
        except queue.Full:
            # 큐가 가득 찬 경우 스킵
            self.stats['skipped_frames'] += 1
            result = ProcessingResult(
                frame_id=frame_id,
                timestamp=timestamp,
                processing_time=0,
                result={'skipped': True, 'reason': 'queue_full'},
                skipped=True
            )
            self.result_queue.put(result)

        return frame_id

    def get_result(self, timeout: float = 0.001) -> Optional[ProcessingResult]:
        """
        처리 결과 가져오기 (논블로킹)

        Args:
            timeout: 타임아웃 (초)

        Returns:
            처리 결과 또는 None
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_all_results(self) -> list:
        """모든 처리 결과 가져오기"""
        results = []
        while True:
            result = self.get_result()
            if result is None:
                break
            results.append(result)
        return results

    def _should_skip_frame(self, current_time: float) -> bool:
        """
        프레임 스킵 여부 결정

        Args:
            current_time: 현재 시간

        Returns:
            스킵 여부
        """
        # 첫 프레임은 처리
        if self.last_process_time == 0:
            return False

        # 이전 처리 이후 경과 시간
        elapsed = current_time - self.last_process_time

        # 33ms 이내면 스킵 (30fps 유지)
        if elapsed < self.skip_threshold:
            return True

        # 큐가 많이 쌓여있으면 스킵
        if self.task_queue.qsize() > 5:
            return True

        return False

    def _worker_loop(self):
        """워커 루프 (백그라운드 스레드)"""
        while self.is_running:
            try:
                # 태스크 가져오기
                priority, frame_id, task = self.task_queue.get(timeout=0.1)

                # 처리 시작
                start_time = time.perf_counter()

                # 실제 처리
                result = self._process_task(task)

                # 처리 시간 계산
                process_time = time.perf_counter() - start_time
                self.last_process_time = time.perf_counter()

                # 통계 업데이트
                self.stats['processed_frames'] += 1
                self.stats['total_process_time'] += process_time
                self.stats['avg_process_time'] = (
                    self.stats['total_process_time'] / self.stats['processed_frames']
                )

                # 결과 생성
                processing_result = ProcessingResult(
                    frame_id=task.frame_id,
                    timestamp=task.timestamp,
                    processing_time=process_time,
                    result=result,
                    skipped=False
                )

                # 결과 큐에 추가
                self.result_queue.put(processing_result)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[AsyncProcessor] 처리 오류: {e}")

    def _process_task(self, task: FrameTask) -> Dict[str, Any]:
        """
        태스크 처리

        Args:
            task: 처리할 태스크

        Returns:
            처리 결과
        """
        try:
            # FrameProcessor 호출
            result = self.frame_processor.process_frame(
                task.frame,
                ref_id=task.ref_id
            )

            # 프레임 ID와 우선순위 추가
            if result:
                result['frame_id'] = task.frame_id
                result['priority'] = task.priority

            return result or {}

        except Exception as e:
            print(f"[AsyncProcessor] 태스크 처리 실패: {e}")
            return {'error': str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        skip_rate = (
            self.stats['skipped_frames'] / max(1, self.stats['total_frames'])
            * 100
        )

        return {
            'total_frames': self.stats['total_frames'],
            'processed_frames': self.stats['processed_frames'],
            'skipped_frames': self.stats['skipped_frames'],
            'skip_rate': skip_rate,
            'avg_process_time_ms': self.stats['avg_process_time'] * 1000,
            'queue_size': self.task_queue.qsize(),
            'result_queue_size': self.result_queue.qsize()
        }

    def clear_queues(self):
        """큐 비우기"""
        # 태스크 큐 비우기
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break

        # 결과 큐 비우기
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break


class AdaptiveFrameSkipper:
    """
    적응형 프레임 스킵 관리자

    처리 속도에 따라 동적으로 스킵 레이트 조정
    """

    def __init__(self, target_fps: float = 30.0):
        """
        초기화

        Args:
            target_fps: 목표 FPS
        """
        self.target_fps = target_fps
        self.target_frame_time = 1.0 / target_fps

        # 스킵 레벨 (0=스킵 없음, 1=1프레임 스킵, 2=2프레임 스킵)
        self.skip_level = 0
        self.frame_counter = 0

        # 성능 추적
        self.recent_times = []
        self.window_size = 10

    def should_process(self, current_time: float) -> bool:
        """
        현재 프레임 처리 여부 결정

        Args:
            current_time: 현재 시간

        Returns:
            처리 여부
        """
        self.frame_counter += 1

        # 스킵 레벨에 따른 처리
        if self.skip_level == 0:
            # 모든 프레임 처리
            return True
        elif self.skip_level == 1:
            # 홀수 프레임만 처리
            return self.frame_counter % 2 == 1
        elif self.skip_level == 2:
            # 3프레임 중 1개만 처리
            return self.frame_counter % 3 == 1
        else:
            # 4프레임 중 1개만 처리
            return self.frame_counter % 4 == 1

    def update_performance(self, process_time: float):
        """
        성능 업데이트 및 스킵 레벨 조정

        Args:
            process_time: 처리 시간
        """
        # 최근 처리 시간 추가
        self.recent_times.append(process_time)
        if len(self.recent_times) > self.window_size:
            self.recent_times.pop(0)

        # 평균 처리 시간 계산
        avg_time = sum(self.recent_times) / len(self.recent_times)

        # 스킵 레벨 조정
        if avg_time < self.target_frame_time * 0.7:
            # 처리가 빠름 - 스킵 줄이기
            self.skip_level = max(0, self.skip_level - 1)
        elif avg_time > self.target_frame_time * 1.2:
            # 처리가 느림 - 스킵 늘리기
            self.skip_level = min(3, self.skip_level + 1)

    def get_effective_fps(self) -> float:
        """실효 FPS 계산"""
        if self.skip_level == 0:
            return self.target_fps
        elif self.skip_level == 1:
            return self.target_fps / 2
        elif self.skip_level == 2:
            return self.target_fps / 3
        else:
            return self.target_fps / 4

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        avg_time = sum(self.recent_times) / len(self.recent_times) if self.recent_times else 0

        return {
            'skip_level': self.skip_level,
            'effective_fps': self.get_effective_fps(),
            'avg_process_time_ms': avg_time * 1000,
            'frames_processed': self.frame_counter
        }


# 테스트
if __name__ == "__main__":
    import cv2
    from frame_processor import FrameProcessor
    from ..core.smart_feedback_v7 import SmartFeedbackV7
    from cache_manager import CacheManager

    print("=== 비동기 처리 테스트 ===")

    # 시스템 초기화
    feedback_system = SmartFeedbackV7(mode='ios')
    cache_manager = CacheManager()
    frame_processor = FrameProcessor(feedback_system, cache_manager)

    # 비동기 프로세서
    async_processor = AsyncFrameProcessor(frame_processor)
    async_processor.start()

    # 적응형 스킵퍼
    skipper = AdaptiveFrameSkipper(target_fps=30)

    # 테스트 이미지
    test_image = np.zeros((640, 640, 3), dtype=np.uint8)

    print("\n프레임 제출 중...")
    for i in range(100):
        current_time = time.perf_counter()

        # 적응형 스킵
        if skipper.should_process(current_time):
            frame_id = async_processor.submit_frame(test_image)

            # 결과 확인 (논블로킹)
            result = async_processor.get_result()
            if result:
                skipper.update_performance(result.processing_time)

                if i % 10 == 0:
                    print(f"프레임 {result.frame_id}: {result.processing_time*1000:.1f}ms")

        # 30fps 시뮬레이션
        time.sleep(0.033)

    # 통계 출력
    print("\n=== 통계 ===")
    async_stats = async_processor.get_stats()
    print(f"총 프레임: {async_stats['total_frames']}")
    print(f"처리된 프레임: {async_stats['processed_frames']}")
    print(f"스킵된 프레임: {async_stats['skipped_frames']} ({async_stats['skip_rate']:.1f}%)")
    print(f"평균 처리 시간: {async_stats['avg_process_time_ms']:.1f}ms")

    skipper_stats = skipper.get_stats()
    print(f"\n스킵 레벨: {skipper_stats['skip_level']}")
    print(f"실효 FPS: {skipper_stats['effective_fps']:.1f}")

    # 정리
    async_processor.stop()