# ============================================================
# TryAngle v1.5 - RTMPose Wrapper
# 포즈 추정 (133 keypoints) 및 Pose Type 판정
# ============================================================

import torch
import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# COCO 17 keypoint 인덱스 (기본)
COCO_KEYPOINTS = {
    0: "nose",
    1: "left_eye",
    2: "right_eye",
    3: "left_ear",
    4: "right_ear",
    5: "left_shoulder",
    6: "right_shoulder",
    7: "left_elbow",
    8: "right_elbow",
    9: "left_wrist",
    10: "right_wrist",
    11: "left_hip",
    12: "right_hip",
    13: "left_knee",
    14: "right_knee",
    15: "left_ankle",
    16: "right_ankle"
}

# 핵심 관절 그룹
UPPER_BODY_JOINTS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 코 ~ 손목
LOWER_BODY_JOINTS = [11, 12, 13, 14, 15, 16]            # 골반 ~ 발목


@dataclass
class Keypoint:
    """단일 키포인트"""
    x: float                  # normalized [0-1]
    y: float                  # normalized [0-1]
    confidence: float
    name: str


@dataclass
class RTMPoseOutput:
    """RTMPose 출력"""
    keypoints: List[Keypoint]
    bbox: Optional[Tuple[float, float, float, float]]  # (x1, y1, x2, y2) normalized
    bbox_confidence: float
    pose_type: str            # closeup, upper_body, half_body, full_body
    angle_estimation: Dict    # 앵글 추정 정보
    raw_keypoints: np.ndarray  # (17, 3) or (133, 3)


class RTMPoseWrapper:
    """
    RTMPose 모델 래퍼 (MMPose 기반)

    Usage:
        wrapper = RTMPoseWrapper(device="cuda")
        result = wrapper.predict(image)
    """

    def __init__(
        self,
        config: str = "rtmpose-l_8xb256-420e_body8-256x192",
        checkpoint: Optional[str] = None,
        device: str = "cuda",
        confidence_threshold: float = 0.3
    ):
        self.config = config
        self.checkpoint = checkpoint
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.detector = None

    def load(self):
        """모델 로드 (MMPose)"""
        try:
            from mmpose.apis import init_model as init_pose_model
            from mmpose.apis import inference_topdown
            from mmdet.apis import init_detector, inference_detector

            # RTMDet (person detector)
            det_config = "rtmdet_m_640-8xb32_coco-person.py"
            det_checkpoint = "rtmdet_m_8xb32-100e_coco-obj365-person.pth"

            self.detector = init_detector(
                det_config, det_checkpoint, device=self.device
            )

            # RTMPose
            pose_config = f"configs/body_2d_keypoint/rtmpose/{self.config}.py"
            self.model = init_pose_model(
                pose_config, self.checkpoint, device=self.device
            )

            self._use_mmpose = True
            print(f"[RTMPose] Loaded MMPose model on {self.device}")

        except ImportError:
            # Fallback: 단순화된 YOLO-Pose 또는 자체 구현
            print("[RTMPose] MMPose not found, using simplified inference")
            self._use_mmpose = False
            self._load_fallback()

    def _load_fallback(self):
        """Fallback 모델 (YOLO-Pose 등)"""
        try:
            from ultralytics import YOLO
            self.model = YOLO("yolo11n-pose.pt")
            self._use_yolo = True
            print(f"[RTMPose] Fallback to YOLO-Pose")
        except ImportError:
            self._use_yolo = False
            print("[RTMPose] Warning: No pose model available")

    def predict(self, image: Image.Image) -> RTMPoseOutput:
        """
        이미지에서 포즈 추정

        Args:
            image: PIL Image

        Returns:
            RTMPoseOutput
        """
        if self.model is None:
            self.load()

        width, height = image.size

        if self._use_mmpose:
            return self._predict_mmpose(image, width, height)
        elif hasattr(self, '_use_yolo') and self._use_yolo:
            return self._predict_yolo(image, width, height)
        else:
            return self._empty_result()

    def _predict_mmpose(self, image: Image.Image, width: int, height: int) -> RTMPoseOutput:
        """MMPose를 사용한 추론"""
        from mmpose.apis import inference_topdown
        from mmdet.apis import inference_detector
        import cv2

        # PIL to numpy BGR
        img_np = np.array(image)
        if len(img_np.shape) == 2:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
        elif img_np.shape[2] == 4:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        else:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Person detection
        det_results = inference_detector(self.detector, img_np)
        person_bboxes = det_results.pred_instances.bboxes.cpu().numpy()
        person_scores = det_results.pred_instances.scores.cpu().numpy()

        if len(person_bboxes) == 0:
            return self._empty_result()

        # 가장 큰 사람 선택
        areas = (person_bboxes[:, 2] - person_bboxes[:, 0]) * \
                (person_bboxes[:, 3] - person_bboxes[:, 1])
        idx = np.argmax(areas)

        bbox = person_bboxes[idx]
        bbox_conf = float(person_scores[idx])

        # Pose estimation
        pose_results = inference_topdown(self.model, img_np, [bbox])

        if len(pose_results) == 0:
            return self._empty_result()

        keypoints_data = pose_results[0].pred_instances.keypoints[0]
        scores = pose_results[0].pred_instances.keypoint_scores[0]

        # Keypoint 리스트 생성
        keypoints = []
        for i, (kp, score) in enumerate(zip(keypoints_data, scores)):
            name = COCO_KEYPOINTS.get(i, f"point_{i}")
            keypoints.append(Keypoint(
                x=float(kp[0]) / width,
                y=float(kp[1]) / height,
                confidence=float(score),
                name=name
            ))

        # Normalize bbox
        norm_bbox = (
            bbox[0] / width,
            bbox[1] / height,
            bbox[2] / width,
            bbox[3] / height
        )

        # Pose type 판정
        pose_type = self._classify_pose_type(keypoints)

        # 앵글 추정
        angle_estimation = self._estimate_angle(keypoints)

        # Raw keypoints array
        raw_kps = np.array([[kp.x, kp.y, kp.confidence] for kp in keypoints])

        return RTMPoseOutput(
            keypoints=keypoints,
            bbox=norm_bbox,
            bbox_confidence=bbox_conf,
            pose_type=pose_type,
            angle_estimation=angle_estimation,
            raw_keypoints=raw_kps
        )

    def _predict_yolo(self, image: Image.Image, width: int, height: int) -> RTMPoseOutput:
        """YOLO-Pose를 사용한 추론 (Fallback)"""
        results = self.model(image, verbose=False)[0]

        if results.keypoints is None or len(results.keypoints) == 0:
            return self._empty_result()

        # 가장 큰 사람 선택
        boxes = results.boxes.xyxy.cpu().numpy()
        if len(boxes) == 0:
            return self._empty_result()

        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        idx = np.argmax(areas)

        bbox = boxes[idx]
        bbox_conf = float(results.boxes.conf[idx])

        kps_data = results.keypoints.xy[idx].cpu().numpy()
        kps_conf = results.keypoints.conf[idx].cpu().numpy()

        # Keypoint 리스트 생성
        keypoints = []
        for i, (kp, score) in enumerate(zip(kps_data, kps_conf)):
            name = COCO_KEYPOINTS.get(i, f"point_{i}")
            keypoints.append(Keypoint(
                x=float(kp[0]) / width if kp[0] > 0 else 0,
                y=float(kp[1]) / height if kp[1] > 0 else 0,
                confidence=float(score),
                name=name
            ))

        # Normalize bbox
        norm_bbox = (
            bbox[0] / width,
            bbox[1] / height,
            bbox[2] / width,
            bbox[3] / height
        )

        pose_type = self._classify_pose_type(keypoints)
        angle_estimation = self._estimate_angle(keypoints)

        raw_kps = np.array([[kp.x, kp.y, kp.confidence] for kp in keypoints])

        return RTMPoseOutput(
            keypoints=keypoints,
            bbox=norm_bbox,
            bbox_confidence=bbox_conf,
            pose_type=pose_type,
            angle_estimation=angle_estimation,
            raw_keypoints=raw_kps
        )

    def _classify_pose_type(self, keypoints: List[Keypoint]) -> str:
        """
        Pose Type 판정

        - closeup: 얼굴 위주 (어깨까지만)
        - upper_body: 상반신 (골반 안 보임)
        - half_body: 반신 (무릎까지)
        - full_body: 전신 (발목까지)
        """
        threshold = self.confidence_threshold

        # 각 부위 가시성 확인
        def is_visible(indices: List[int]) -> bool:
            visible_count = sum(
                1 for i in indices
                if i < len(keypoints) and keypoints[i].confidence >= threshold
            )
            return visible_count >= len(indices) * 0.5

        # 얼굴 (코, 눈, 귀)
        face_visible = is_visible([0, 1, 2, 3, 4])

        # 어깨
        shoulder_visible = is_visible([5, 6])

        # 골반
        hip_visible = is_visible([11, 12])

        # 무릎
        knee_visible = is_visible([13, 14])

        # 발목
        ankle_visible = is_visible([15, 16])

        # 판정 로직
        if ankle_visible:
            return "full_body"
        elif knee_visible:
            return "half_body"
        elif hip_visible:
            return "half_body"  # 골반 보이면 최소 반신
        elif shoulder_visible:
            return "upper_body"
        elif face_visible:
            return "closeup"
        else:
            return "upper_body"  # 기본값 (Conservative)

    def _estimate_angle(self, keypoints: List[Keypoint]) -> Dict:
        """
        카메라 앵글 추정 (keypoint 비율 기반)

        Returns:
            {
                "estimated_angle": float,  # 추정 각도 (- = low angle, + = high angle)
                "confidence": float,
                "method": str
            }
        """
        threshold = self.confidence_threshold
        result = {
            "estimated_angle": 0.0,
            "confidence": 0.0,
            "method": "none"
        }

        # 방법 1: 얼굴 랜드마크 (코-턱 벡터)
        nose = keypoints[0] if len(keypoints) > 0 else None

        # 방법 2: 어깨-골반 비율
        if len(keypoints) >= 13:
            l_shoulder = keypoints[5]
            r_shoulder = keypoints[6]
            l_hip = keypoints[11]
            r_hip = keypoints[12]

            shoulder_conf = min(l_shoulder.confidence, r_shoulder.confidence)
            hip_conf = min(l_hip.confidence, r_hip.confidence)

            if shoulder_conf >= threshold and hip_conf >= threshold:
                # 어깨 중심과 골반 중심
                shoulder_y = (l_shoulder.y + r_shoulder.y) / 2
                hip_y = (l_hip.y + r_hip.y) / 2

                # 상체 길이 비율로 앵글 추정
                torso_length = hip_y - shoulder_y

                # 정면 기준 torso_length 예상값 대비 비율
                # 짧으면 high angle, 길면 low angle
                expected_ratio = 0.25  # 정상적인 상체 비율
                actual_ratio = torso_length

                if actual_ratio > 0:
                    angle_factor = (expected_ratio - actual_ratio) / expected_ratio
                    estimated_angle = angle_factor * 30  # -30 ~ +30도 범위로 매핑

                    result["estimated_angle"] = float(np.clip(estimated_angle, -45, 45))
                    result["confidence"] = float(min(shoulder_conf, hip_conf))
                    result["method"] = "body_keypoints"

        return result

    def _empty_result(self) -> RTMPoseOutput:
        """빈 결과 반환"""
        return RTMPoseOutput(
            keypoints=[],
            bbox=None,
            bbox_confidence=0.0,
            pose_type="upper_body",  # 기본값
            angle_estimation={"estimated_angle": 0, "confidence": 0, "method": "none"},
            raw_keypoints=np.array([])
        )


# ============================================================
# Quick Test
# ============================================================
if __name__ == "__main__":
    from PIL import Image

    wrapper = RTMPoseWrapper(device="cuda")

    # 테스트 이미지
    test_image = Image.new("RGB", (640, 480), color="white")

    result = wrapper.predict(test_image)

    print(f"Pose Type: {result.pose_type}")
    print(f"Bbox: {result.bbox}")
    print(f"Keypoints count: {len(result.keypoints)}")
    print(f"Angle estimation: {result.angle_estimation}")
