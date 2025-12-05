"""
캐시 관리자 - 레퍼런스 분석 결과 캐싱 및 보정 계수 관리
작성일: 2025-12-05
"""

import time
import json
import pickle
from typing import Dict, Optional, Any, Tuple
from pathlib import Path
import numpy as np


class CacheManager:
    """
    레퍼런스 분석 결과 캐싱 및 보정 계수 관리

    주요 기능:
    1. 레퍼런스 분석 결과 저장
    2. RTMPose vs Grounding DINO 보정 계수 계산
    3. 캐시 만료 관리
    """

    def __init__(self, cache_dir: Optional[str] = None, cache_timeout: int = 3600):
        """
        초기화
        Args:
            cache_dir: 캐시 저장 디렉토리 (None이면 메모리만 사용)
            cache_timeout: 캐시 만료 시간 (초, 기본 1시간)
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_timeout = cache_timeout

        # 메모리 캐시
        self.memory_cache = {}
        self.calibration_factors = {}
        self.cache_timestamps = {}

        # 캐시 디렉토리 생성
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_reference(self, ref_id: str, analysis_result: Dict[str, Any]) -> bool:
        """
        레퍼런스 분석 결과 캐싱

        Args:
            ref_id: 레퍼런스 ID (파일명 또는 해시)
            analysis_result: 분석 결과 딕셔너리

        Returns:
            성공 여부
        """
        try:
            # 타임스탬프 추가
            analysis_result['cached_at'] = time.time()

            # 메모리 캐시 저장
            self.memory_cache[ref_id] = analysis_result
            self.cache_timestamps[ref_id] = time.time()

            # 파일 캐시 저장 (선택적)
            if self.cache_dir:
                cache_file = self.cache_dir / f"{ref_id}.pkl"
                with open(cache_file, 'wb') as f:
                    pickle.dump(analysis_result, f)

            # 보정 계수 계산 (Legacy와 RTMPose 둘 다 있는 경우)
            if 'legacy_analysis' in analysis_result and 'keypoints' in analysis_result:
                self._calculate_calibration_factor(ref_id, analysis_result)

            return True

        except Exception as e:
            print(f"[CacheManager] 캐싱 실패: {e}")
            return False

    def get_reference(self, ref_id: str) -> Optional[Dict[str, Any]]:
        """
        캐시된 레퍼런스 가져오기

        Args:
            ref_id: 레퍼런스 ID

        Returns:
            캐시된 분석 결과 또는 None
        """
        # 메모리 캐시 확인
        if ref_id in self.memory_cache:
            # 만료 확인
            if self._is_cache_valid(ref_id):
                return self.memory_cache[ref_id]
            else:
                # 만료된 캐시 삭제
                del self.memory_cache[ref_id]
                del self.cache_timestamps[ref_id]

        # 파일 캐시 확인
        if self.cache_dir:
            cache_file = self.cache_dir / f"{ref_id}.pkl"
            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        data = pickle.load(f)

                    # 만료 확인
                    if time.time() - data.get('cached_at', 0) < self.cache_timeout:
                        # 메모리 캐시에 복원
                        self.memory_cache[ref_id] = data
                        self.cache_timestamps[ref_id] = data.get('cached_at', time.time())
                        return data
                    else:
                        # 만료된 파일 삭제
                        cache_file.unlink()

                except Exception as e:
                    print(f"[CacheManager] 파일 캐시 로드 실패: {e}")

        return None

    def get_calibration_factor(self, ref_id: str) -> Dict[str, float]:
        """
        보정 계수 가져오기

        RTMPose bbox와 Grounding DINO bbox의 차이를 보정하는 계수

        Returns:
            {'top': 1.0, 'bottom': 1.0, 'left': 1.0, 'right': 1.0}
        """
        if ref_id in self.calibration_factors:
            return self.calibration_factors[ref_id]
        else:
            # 기본값 (보정 없음)
            return {'top': 1.0, 'bottom': 1.0, 'left': 1.0, 'right': 1.0}

    def _calculate_calibration_factor(self, ref_id: str, analysis_result: Dict):
        """
        보정 계수 계산 (내부 메서드)

        Legacy (Grounding DINO) bbox와 RTMPose bbox의 비율 계산
        """
        try:
            # Legacy bbox (Grounding DINO)
            if 'person_bbox' in analysis_result:
                dino_bbox = analysis_result['person_bbox']  # (x1, y1, x2, y2) normalized
            else:
                return

            # RTMPose bbox 계산
            keypoints = analysis_result.get('keypoints', {})
            if not keypoints:
                return

            # 키포인트에서 bbox 계산
            rtm_bbox = self._calculate_bbox_from_keypoints(keypoints)
            if not rtm_bbox:
                return

            # 보정 계수 계산
            # 여백 비율로 계산
            img_shape = analysis_result.get('image_shape', (1080, 1920))  # (h, w)
            h, w = img_shape[0], img_shape[1]

            # Grounding DINO 여백
            dino_margins = {
                'top': dino_bbox[1],
                'bottom': 1.0 - dino_bbox[3],
                'left': dino_bbox[0],
                'right': 1.0 - dino_bbox[2]
            }

            # RTMPose 여백
            rtm_margins = {
                'top': rtm_bbox[1] / h,
                'bottom': (h - rtm_bbox[3]) / h,
                'left': rtm_bbox[0] / w,
                'right': (w - rtm_bbox[2]) / w
            }

            # 보정 계수 = DINO / RTMPose
            self.calibration_factors[ref_id] = {
                'top': dino_margins['top'] / (rtm_margins['top'] + 0.001),
                'bottom': dino_margins['bottom'] / (rtm_margins['bottom'] + 0.001),
                'left': dino_margins['left'] / (rtm_margins['left'] + 0.001),
                'right': dino_margins['right'] / (rtm_margins['right'] + 0.001)
            }

            print(f"[CacheManager] 보정 계수 계산 완료: {self.calibration_factors[ref_id]}")

        except Exception as e:
            print(f"[CacheManager] 보정 계수 계산 실패: {e}")

    def _calculate_bbox_from_keypoints(self, keypoints: Dict) -> Optional[Tuple[float, float, float, float]]:
        """
        키포인트에서 바운딩 박스 계산

        Returns:
            (x1, y1, x2, y2) in pixels or None
        """
        try:
            all_points = []

            # 모든 키포인트 수집
            for body_part in keypoints.get('body_keypoints', {}).values():
                if 'position' in body_part:
                    all_points.append(body_part['position'])

            if not all_points:
                return None

            points = np.array(all_points)
            x1, y1 = points[:, 0].min(), points[:, 1].min()
            x2, y2 = points[:, 0].max(), points[:, 1].max()

            return (x1, y1, x2, y2)

        except Exception:
            return None

    def _is_cache_valid(self, ref_id: str) -> bool:
        """
        캐시 유효성 확인
        """
        if ref_id not in self.cache_timestamps:
            return False

        elapsed = time.time() - self.cache_timestamps[ref_id]
        return elapsed < self.cache_timeout

    def apply_calibration(self, margins: Dict[str, float], ref_id: str) -> Dict[str, float]:
        """
        RTMPose 여백에 보정 계수 적용

        Args:
            margins: RTMPose로 계산한 여백
            ref_id: 레퍼런스 ID

        Returns:
            보정된 여백
        """
        factors = self.get_calibration_factor(ref_id)

        calibrated = {}
        for key in margins:
            if key in factors:
                calibrated[key] = margins[key] * factors[key]
            else:
                calibrated[key] = margins[key]

        return calibrated

    def clear_cache(self, ref_id: Optional[str] = None):
        """
        캐시 삭제

        Args:
            ref_id: 특정 ID만 삭제 (None이면 전체 삭제)
        """
        if ref_id:
            # 특정 캐시 삭제
            if ref_id in self.memory_cache:
                del self.memory_cache[ref_id]
            if ref_id in self.cache_timestamps:
                del self.cache_timestamps[ref_id]
            if ref_id in self.calibration_factors:
                del self.calibration_factors[ref_id]

            # 파일 삭제
            if self.cache_dir:
                cache_file = self.cache_dir / f"{ref_id}.pkl"
                if cache_file.exists():
                    cache_file.unlink()
        else:
            # 전체 캐시 삭제
            self.memory_cache.clear()
            self.cache_timestamps.clear()
            self.calibration_factors.clear()

            # 모든 캐시 파일 삭제
            if self.cache_dir:
                for cache_file in self.cache_dir.glob("*.pkl"):
                    cache_file.unlink()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 반환
        """
        return {
            'cache_count': len(self.memory_cache),
            'calibration_count': len(self.calibration_factors),
            'cache_dir': str(self.cache_dir) if self.cache_dir else None,
            'timeout_seconds': self.cache_timeout,
            'cached_ids': list(self.memory_cache.keys())
        }


if __name__ == "__main__":
    # 테스트
    cache = CacheManager(cache_timeout=60)

    # 테스트 데이터
    test_analysis = {
        'keypoints': {'body_keypoints': {}},
        'margins': {'top': 0.1, 'bottom': 0.1, 'left': 0.1, 'right': 0.1},
        'image_shape': (1080, 1920)
    }

    # 캐싱 테스트
    cache.cache_reference("test_ref", test_analysis)

    # 가져오기 테스트
    cached = cache.get_reference("test_ref")
    if cached:
        print("캐시 성공!")
        print(f"캐시 통계: {cache.get_cache_stats()}")
    else:
        print("캐시 실패!")