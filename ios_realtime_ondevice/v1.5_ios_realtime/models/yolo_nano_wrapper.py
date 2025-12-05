"""
YOLO v8 Nano - 초경량 객체 검출 모델 래퍼
작성일: 2025-12-05
iOS 실시간 처리용 최적화 버전
"""

import numpy as np
from typing import Optional, Dict, Any, List, Tuple
import time
import cv2


class YOLONano:
    """
    YOLO v8 Nano 모델 래퍼

    특징:
    - 모델 크기: ~6MB
    - 처리 시간: 10-15ms (목표)
    - 정확도: 인물 검출에 충분
    """

    def __init__(self, model_path: Optional[str] = None,
                 confidence_threshold: float = 0.5,
                 nms_threshold: float = 0.4,
                 device: str = 'cpu'):
        """
        초기화

        Args:
            model_path: 모델 파일 경로
            confidence_threshold: 검출 신뢰도 임계값
            nms_threshold: Non-Maximum Suppression 임계값
            device: 'cpu' or 'cuda'
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.device = device
        self.model = None
        self.model_loaded = False

        # COCO 클래스 (person = 0)
        self.class_names = {
            0: 'person',
            # 다른 클래스는 필요시 추가
        }

        # 성능 통계
        self.stats = {
            'total_detections': 0,
            'total_time': 0,
            'avg_time': 0
        }

    def load_model(self):
        """모델 로드 (지연 로딩)"""
        if self.model_loaded:
            return True

        try:
            # 방법 1: ultralytics 패키지 사용 (권장)
            try:
                from ultralytics import YOLO

                # YOLOv8n 모델 로드
                if self.model_path:
                    self.model = YOLO(self.model_path)
                else:
                    # 자동 다운로드
                    self.model = YOLO('yolov8n.pt')

                # 디바이스 설정
                if self.device == 'cuda' and not self.model.device.type == 'cuda':
                    self.model.to('cuda')

                self.model_loaded = True
                print("[YOLONano] ultralytics YOLO 모델 로드 성공")
                return True

            except ImportError:
                print("[YOLONano] ultralytics 패키지 없음, OpenCV DNN 시도")

            # 방법 2: OpenCV DNN 사용 (대체)
            try:
                import cv2

                # ONNX 모델 경로
                if self.model_path and self.model_path.endswith('.onnx'):
                    self.model = cv2.dnn.readNetFromONNX(self.model_path)
                else:
                    # 기본 경로 시도
                    self.model = cv2.dnn.readNetFromONNX('yolov8n.onnx')

                # 백엔드 설정
                self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                if self.device == 'cuda':
                    self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                else:
                    self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

                self.model_loaded = True
                self.use_opencv = True
                print("[YOLONano] OpenCV DNN 모델 로드 성공")
                return True

            except Exception as e:
                print(f"[YOLONano] OpenCV DNN 로드 실패: {e}")

            # 방법 3: 더미 모드 (테스트용)
            print("[YOLONano] 경고: 더미 모드로 실행 (실제 검출 없음)")
            self.model = None
            self.model_loaded = True
            return True

        except Exception as e:
            print(f"[YOLONano] 모델 로드 실패: {e}")
            return False

    def detect_person(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        프레임에서 가장 큰 person bbox 반환

        Args:
            frame: 입력 프레임 (H, W, C) BGR 형식

        Returns:
            (x1, y1, x2, y2) in pixels or None
        """
        detections = self.detect_all(frame, classes=[0])  # person만

        if detections:
            # 가장 큰 bbox 선택 (면적 기준)
            largest = max(detections,
                         key=lambda d: (d['bbox'][2] - d['bbox'][0]) * (d['bbox'][3] - d['bbox'][1]))
            return largest['bbox']
        return None

    def detect_all(self, frame: np.ndarray,
                  classes: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        프레임에서 모든 객체 검출

        Args:
            frame: 입력 프레임 (H, W, C) BGR 형식
            classes: 검출할 클래스 ID 리스트 (None이면 모든 클래스)

        Returns:
            검출 결과 리스트
        """
        if not self.model_loaded:
            if not self.load_model():
                return []

        start_time = time.perf_counter()
        detections = []

        try:
            # 더미 모드
            if self.model is None:
                # 테스트용 더미 검출
                h, w = frame.shape[:2]
                dummy_bbox = (w//4, h//4, 3*w//4, 3*h//4)
                detections = [{
                    'bbox': dummy_bbox,
                    'confidence': 0.95,
                    'class': 0,
                    'label': 'person'
                }]

            # ultralytics YOLO 사용
            elif hasattr(self.model, 'predict'):
                results = self.model.predict(
                    frame,
                    conf=self.confidence_threshold,
                    iou=self.nms_threshold,
                    classes=classes,
                    verbose=False
                )

                if results and len(results) > 0:
                    result = results[0]
                    if result.boxes is not None:
                        boxes = result.boxes
                        for i in range(len(boxes)):
                            box = boxes.xyxy[i].cpu().numpy()
                            conf = float(boxes.conf[i])
                            cls = int(boxes.cls[i])

                            # 클래스 필터링
                            if classes is None or cls in classes:
                                detections.append({
                                    'bbox': tuple(box.astype(int)),
                                    'confidence': conf,
                                    'class': cls,
                                    'label': self.class_names.get(cls, f'class_{cls}')
                                })

            # OpenCV DNN 사용
            elif hasattr(self, 'use_opencv') and self.use_opencv:
                detections = self._detect_opencv(frame, classes)

            self._update_stats(time.perf_counter() - start_time)

        except Exception as e:
            print(f"[YOLONano] 검출 오류: {e}")

        return detections

    def _detect_opencv(self, frame: np.ndarray,
                      classes: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        OpenCV DNN으로 검출 (내부 메서드)
        """
        h, w = frame.shape[:2]

        # 전처리
        blob = cv2.dnn.blobFromImage(
            frame, 1/255.0, (640, 640),
            swapRB=True, crop=False
        )

        self.model.setInput(blob)
        outputs = self.model.forward()

        # YOLOv8 출력 파싱
        detections = []

        # 출력 형식: [1, 84, 8400] (84 = 4 bbox + 80 classes)
        if outputs.shape[1] == 84:  # YOLOv8
            outputs = outputs[0].T  # [8400, 84]

            boxes = outputs[:, :4]
            scores = outputs[:, 4:]

            for i in range(len(boxes)):
                class_scores = scores[i]
                max_score = np.max(class_scores)

                if max_score < self.confidence_threshold:
                    continue

                class_id = np.argmax(class_scores)

                # 클래스 필터링
                if classes is not None and class_id not in classes:
                    continue

                # 박스 변환 (center x, y, w, h -> x1, y1, x2, y2)
                cx, cy, bw, bh = boxes[i]
                x1 = int((cx - bw/2) * w / 640)
                y1 = int((cy - bh/2) * h / 640)
                x2 = int((cx + bw/2) * w / 640)
                y2 = int((cy + bh/2) * h / 640)

                detections.append({
                    'bbox': (x1, y1, x2, y2),
                    'confidence': float(max_score),
                    'class': int(class_id),
                    'label': self.class_names.get(class_id, f'class_{class_id}')
                })

        # NMS 적용
        if detections:
            detections = self._apply_nms(detections)

        return detections

    def _apply_nms(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Non-Maximum Suppression 적용
        """
        if not detections:
            return detections

        boxes = np.array([d['bbox'] for d in detections])
        scores = np.array([d['confidence'] for d in detections])

        # OpenCV NMS
        indices = cv2.dnn.NMSBoxes(
            boxes.tolist(),
            scores.tolist(),
            self.confidence_threshold,
            self.nms_threshold
        )

        if indices is not None and len(indices) > 0:
            indices = indices.flatten()
            return [detections[i] for i in indices]

        return []

    def calculate_bbox_from_keypoints(self, keypoints: np.ndarray,
                                     padding: float = 0.1) -> Optional[Tuple[int, int, int, int]]:
        """
        키포인트에서 바운딩 박스 계산 (보조 기능)

        Args:
            keypoints: 키포인트 배열
            padding: 패딩 비율

        Returns:
            (x1, y1, x2, y2) or None
        """
        if keypoints is None or len(keypoints) == 0:
            return None

        valid_points = keypoints[keypoints[:, 2] > 0]  # confidence > 0
        if len(valid_points) == 0:
            return None

        x_coords = valid_points[:, 0]
        y_coords = valid_points[:, 1]

        x_min, x_max = np.min(x_coords), np.max(x_coords)
        y_min, y_max = np.min(y_coords), np.max(y_coords)

        # 패딩 추가
        width = x_max - x_min
        height = y_max - y_min

        x_min -= width * padding
        x_max += width * padding
        y_min -= height * padding
        y_max += height * padding

        return (int(x_min), int(y_min), int(x_max), int(y_max))

    def _update_stats(self, process_time: float):
        """통계 업데이트"""
        self.stats['total_detections'] += 1
        self.stats['total_time'] += process_time
        self.stats['avg_time'] = self.stats['total_time'] / self.stats['total_detections']

    def get_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        return {
            'total_detections': self.stats['total_detections'],
            'avg_time_ms': self.stats['avg_time'] * 1000,
            'model_loaded': self.model_loaded,
            'device': self.device,
            'confidence_threshold': self.confidence_threshold
        }

    def warmup(self, dummy_frame: Optional[np.ndarray] = None):
        """
        모델 워밍업 (첫 추론 지연 방지)
        """
        if dummy_frame is None:
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)

        print("[YOLONano] 워밍업 중...")
        for _ in range(3):
            _ = self.detect_person(dummy_frame)
        print(f"[YOLONano] 워밍업 완료 (평균: {self.stats['avg_time']*1000:.1f}ms)")


# 간단한 테스트
if __name__ == "__main__":
    detector = YOLONano(confidence_threshold=0.5, device='cpu')

    # 더미 프레임 테스트
    dummy = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

    # 워밍업
    detector.warmup(dummy)

    # 실제 테스트
    bbox = detector.detect_person(dummy)

    if bbox:
        print(f"Person bbox: {bbox}")
        print(f"성능: {detector.get_stats()}")
    else:
        print("Person 검출 실패")