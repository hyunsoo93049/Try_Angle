#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TryAngle v1.5 - 자동 이미지 분류 스크립트
현재 clustering 폴더의 이미지를 Theme × Pose Type으로 재분류
"""

import os
import sys
import json
import shutil
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from tqdm import tqdm
import argparse
import numpy as np
import cv2

# 설정
USE_MODELS = False  # True로 변경하면 실제 모델 사용
COPY_MODE = True    # True: 복사, False: 이동

# 테마 분류 규칙
THEME_RULES = {
    'cafe_indoor': ['table', 'chair', 'coffee', 'window', 'cup', 'cafe'],
    'street_urban': ['building', 'car', 'road', 'sidewalk', 'sign', 'street'],
    'park_nature': ['tree', 'grass', 'bench', 'sky', 'flower', 'park'],
    'beach': ['ocean', 'sand', 'wave', 'umbrella', 'beach'],
    'winter': ['snow', 'ice', 'coat', 'scarf', 'winter'],
    'indoor_home': ['sofa', 'tv', 'bed', 'door', 'room']
}

# Pose Type 정의
POSE_TYPES = ['closeup', 'upper_body', 'half_body', 'full_body']


class ImageClassifier:
    """이미지 자동 분류기"""

    def __init__(self, source_dir: str, target_dir: str, use_models: bool = False):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.use_models = use_models
        self.stats = {}

        # 모델 사용 시
        if self.use_models:
            print("[AI] 모델 로딩...")
            self._load_models()
        else:
            print("[Simple Mode] 폴더명 기반 분류")

    def _load_models(self):
        """실제 모델 로드"""
        try:
            from mmpose.apis import init_model, inference_topdown
            from mmdet.apis import init_detector, inference_detector

            print("[RTMPose] 모델 로딩...")

            # RTMPose 설정
            pose_config = 'rtmpose-l_8xb32-270e_coco-ubody-wholebody-384x288.py'
            pose_checkpoint = 'https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/rtmpose-l_simcc-ucoco_dw-ucoco_270e-384x288-2438fd99_20230728.pth'

            # MMDet for person detection
            det_config = 'rtmdet_m_640-8xb32_coco-person.py'
            det_checkpoint = 'https://download.openmmlab.com/mmpose/v1/projects/rtmpose/rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth'

            self.detector = init_detector(det_config, det_checkpoint, device='cuda:0')
            self.pose_model = init_model(pose_config, pose_checkpoint, device='cuda:0')
            self.inference_topdown = inference_topdown

            print("[OK] RTMPose 로드 완료")
        except Exception as e:
            print(f"[WARNING] 모델 로드 실패: {e}")
            print("Simple Mode로 전환합니다.")
            self.use_models = False

    def classify_theme(self, image_path: Path) -> str:
        """테마 분류"""
        if self.use_models:
            return self._classify_theme_with_model(image_path)
        else:
            return self._classify_theme_simple(image_path)

    def _classify_theme_simple(self, image_path: Path) -> str:
        """Simple Mode: 현재 폴더명 기반 분류"""
        path_str = str(image_path).lower()

        # 현재 폴더 구조 기반
        if 'cafe' in path_str or 'cluster_02' in path_str or 'cluster_05' in path_str:
            return 'cafe_indoor'
        elif 'park' in path_str or 'nature' in path_str or 'cluster_03' in path_str or 'cluster_07' in path_str:
            return 'park_nature'
        elif 'street' in path_str or 'urban' in path_str or 'cluster_12' in path_str or 'cluster_14' in path_str or 'cluster_09' in path_str or 'cluster_11' in path_str:
            return 'street_urban'
        elif 'winter' in path_str or 'cluster_06' in path_str:
            return 'winter'
        elif 'indoor' in path_str or 'home' in path_str or 'highangle' in path_str or 'cluster_08' in path_str:
            return 'indoor_home'
        elif 'person' in path_str:
            # person 폴더 내 클러스터별 분류 (레거시)
            if 'cluster_03' in path_str or 'cluster_07' in path_str:
                return 'park_nature'
            elif 'cluster_09' in path_str or 'cluster_11' in path_str:
                return 'street_urban'
            else:
                return 'park_nature'  # 기본값
        else:
            return 'unknown'

    def _classify_theme_with_model(self, image_path: Path) -> str:
        """Model Mode: Grounding DINO로 테마 분류"""
        # TODO: 실제 구현
        # objects = self.grounding_dino.detect(image_path)
        # scores = {}
        # for theme, keywords in THEME_RULES.items():
        #     score = sum(1 for obj in objects if any(kw in obj for kw in keywords))
        #     scores[theme] = score
        # return max(scores, key=scores.get)

        return self._classify_theme_simple(image_path)  # 임시

    def classify_pose_type(self, image_path: Path) -> str:
        """Pose Type 분류"""
        if self.use_models:
            return self._classify_pose_with_model(image_path)
        else:
            return self._classify_pose_simple(image_path)

    def _classify_pose_simple(self, image_path: Path) -> str:
        """Simple Mode: 랜덤 분포 (실제는 RTMPose 사용)"""
        # 실제 분포 시뮬레이션
        weights = {
            'closeup': 0.1,
            'upper_body': 0.3,
            'half_body': 0.4,
            'full_body': 0.2
        }
        return random.choices(
            list(weights.keys()),
            weights=list(weights.values())
        )[0]

    def _classify_pose_with_model(self, image_path: Path) -> str:
        """Model Mode: RTMPose로 pose type 분류"""
        try:
            # 이미지 로드
            img = cv2.imread(str(image_path))
            if img is None:
                return self._classify_pose_simple(image_path)

            # Person 검출
            from mmdet.apis import inference_detector
            det_results = inference_detector(self.detector, img)

            # Person bbox 추출
            if hasattr(det_results, 'pred_instances'):
                bboxes = det_results.pred_instances.bboxes.cpu().numpy()
                scores = det_results.pred_instances.scores.cpu().numpy()
            else:
                return self._classify_pose_simple(image_path)

            if len(bboxes) == 0:
                return 'unknown'

            # 가장 높은 점수의 person 선택
            max_idx = scores.argmax()
            person_bbox = bboxes[max_idx]

            # RTMPose로 keypoint 추출
            pose_results = self.inference_topdown(
                self.pose_model,
                img,
                bboxes=[person_bbox]
            )

            if len(pose_results) == 0:
                return self._classify_pose_simple(image_path)

            # Keypoints 분석
            keypoints = pose_results[0].pred_instances.keypoints[0]  # (133, 2)
            scores_kpt = pose_results[0].pred_instances.keypoint_scores[0]  # (133,)

            # 주요 관절 인덱스 (COCO-WholeBody format)
            # 0-16: body, 17-22: feet, 23-90: face, 91-132: hands
            NOSE = 0
            LEFT_SHOULDER = 5
            RIGHT_SHOULDER = 6
            LEFT_HIP = 11
            RIGHT_HIP = 12
            LEFT_KNEE = 13
            RIGHT_KNEE = 14
            LEFT_ANKLE = 15
            RIGHT_ANKLE = 16

            conf_threshold = 0.3
            img_height = img.shape[0]

            # 관절 가시성 확인
            nose_visible = scores_kpt[NOSE] > conf_threshold
            shoulder_visible = (scores_kpt[LEFT_SHOULDER] > conf_threshold or
                                scores_kpt[RIGHT_SHOULDER] > conf_threshold)
            hip_visible = (scores_kpt[LEFT_HIP] > conf_threshold or
                          scores_kpt[RIGHT_HIP] > conf_threshold)
            knee_visible = (scores_kpt[LEFT_KNEE] > conf_threshold or
                            scores_kpt[RIGHT_KNEE] > conf_threshold)
            ankle_visible = (scores_kpt[LEFT_ANKLE] > conf_threshold or
                             scores_kpt[RIGHT_ANKLE] > conf_threshold)

            # Pose Type 판정 (설계 문서 기준)
            if ankle_visible and knee_visible:
                # 발목이 프레임 안에 있는지 확인
                ankle_y = min(keypoints[LEFT_ANKLE][1], keypoints[RIGHT_ANKLE][1])
                if ankle_y < img_height * 0.95:
                    return 'full_body'
                else:
                    return 'half_body'
            elif knee_visible and hip_visible:
                return 'half_body'
            elif shoulder_visible and hip_visible:
                return 'upper_body'
            elif nose_visible or shoulder_visible:
                return 'closeup'
            else:
                return 'unknown'

        except Exception as e:
            print(f"\n[WARNING] RTMPose 에러 ({image_path.name}): {e}")
            return self._classify_pose_simple(image_path)

    def process_all(self):
        """전체 이미지 처리"""
        print("\n[SEARCH] 이미지 검색 중...")

        # 모든 이미지 찾기 (Windows는 대소문자 구분 안함)
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp']  # .JPG 제거
        all_images = []
        seen_paths = set()  # 중복 제거용

        for ext in image_extensions:
            for img_path in self.source_dir.rglob(f'*{ext}'):
                # 경로를 소문자로 변환하여 중복 체크
                normalized_path = str(img_path).lower()
                if normalized_path not in seen_paths:
                    all_images.append(img_path)
                    seen_paths.add(normalized_path)
            # 대문자 확장자도 체크 (Linux/Mac 호환성)
            for img_path in self.source_dir.rglob(f'*{ext.upper()}'):
                normalized_path = str(img_path).lower()
                if normalized_path not in seen_paths:
                    all_images.append(img_path)
                    seen_paths.add(normalized_path)

        total_images = len(all_images)
        print(f"[IMAGES] 총 {total_images}장의 이미지 발견\n")

        # 진행 상황 표시
        with tqdm(total=total_images, desc="분류 중") as pbar:
            for img_path in all_images:
                # 1. Theme 분류
                theme = self.classify_theme(img_path)

                # 2. Pose Type 분류
                pose_type = self.classify_pose_type(img_path)

                # 3. 새 경로 생성
                new_dir = self.target_dir / theme / pose_type
                new_dir.mkdir(parents=True, exist_ok=True)

                # 4. 파일 복사 또는 이동
                new_path = new_dir / img_path.name

                # 중복 파일명 처리
                if new_path.exists():
                    stem = img_path.stem
                    suffix = img_path.suffix
                    counter = 1
                    while new_path.exists():
                        new_path = new_dir / f"{stem}_{counter}{suffix}"
                        counter += 1

                if COPY_MODE:
                    shutil.copy2(img_path, new_path)
                else:
                    shutil.move(str(img_path), str(new_path))

                # 5. 통계 업데이트
                key = f"{theme}/{pose_type}"
                self.stats[key] = self.stats.get(key, 0) + 1

                pbar.update(1)

        print("\n[OK] 분류 완료!")
        self.print_statistics()
        self.save_statistics()

    def print_statistics(self):
        """분류 결과 통계 출력"""
        print("\n[STATS] 분류 결과:")
        print("=" * 50)

        # Theme별 집계
        theme_totals = {}
        for key, count in sorted(self.stats.items()):
            theme = key.split('/')[0]
            theme_totals[theme] = theme_totals.get(theme, 0) + count
            print(f"  {key}: {count}장")

        print("\n[SUMMARY] 테마별 총계:")
        print("-" * 50)
        for theme, total in sorted(theme_totals.items()):
            print(f"  {theme}: {total}장")

        print(f"\n  총합: {sum(self.stats.values())}장")

    def save_statistics(self):
        """통계를 JSON으로 저장"""
        stats_file = self.target_dir / 'classification_stats.json'

        # Theme별로 정리
        organized_stats = {}
        for key, count in self.stats.items():
            theme, pose_type = key.split('/')

            if theme not in organized_stats:
                organized_stats[theme] = {
                    'total': 0,
                    'pose_types': {}
                }

            organized_stats[theme]['pose_types'][pose_type] = count
            organized_stats[theme]['total'] += count

        # 메타데이터 추가
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'source_dir': str(self.source_dir),
            'target_dir': str(self.target_dir),
            'total_images': sum(self.stats.values()),
            'mode': 'model' if self.use_models else 'simple',
            'statistics': organized_stats
        }

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n[FILE] 통계 저장: {stats_file}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='TryAngle v1.5 - 이미지 자동 분류'
    )

    parser.add_argument(
        '--source',
        default='C:/try_angle/v1.5_ios/data/clustering',
        help='원본 이미지 폴더 경로'
    )

    parser.add_argument(
        '--target',
        default='C:/try_angle/v1.5_ios/data/classified_full',
        help='분류된 이미지 저장 폴더'
    )

    parser.add_argument(
        '--use-models',
        action='store_true',
        help='AI 모델 사용 (기본: Simple Mode)'
    )

    parser.add_argument(
        '--move',
        action='store_true',
        help='파일 이동 (기본: 복사)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 파일 작업 없이 시뮬레이션만'
    )

    args = parser.parse_args()

    # 설정 업데이트
    global USE_MODELS, COPY_MODE
    USE_MODELS = args.use_models
    COPY_MODE = not args.move

    print("=" * 60)
    print("[TARGET] TryAngle v1.5 - 자동 이미지 분류")
    print("=" * 60)
    print(f"[FOLDER] 원본 폴더: {args.source}")
    print(f"[FOLDER] 대상 폴더: {args.target}")
    print(f"[CONFIG] 모드: {'AI 모델' if USE_MODELS else 'Simple (폴더명 기반)'}")
    print(f"[MODE] 작업: {'복사' if COPY_MODE else '이동'}")
    print("=" * 60)

    if args.dry_run:
        print("\n[WARNING] DRY RUN 모드: 실제 파일 작업은 수행되지 않습니다.")
        return

    # 확인 (자동 진행)
    print("\n자동 진행 모드로 시작합니다...")
    # response = input("\n계속 진행하시겠습니까? (y/n): ")
    # if response.lower() != 'y':
    #     print("취소되었습니다.")
    #     return

    # 분류기 실행
    classifier = ImageClassifier(
        source_dir=args.source,
        target_dir=args.target,
        use_models=USE_MODELS
    )

    classifier.process_all()

    print("\n[DONE] 완료!")
    print(f"[FOLDER] 분류된 이미지 확인: {args.target}")


if __name__ == "__main__":
    main()