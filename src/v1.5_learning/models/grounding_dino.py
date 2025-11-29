# ============================================================
# TryAngle v1.5 - Grounding DINO Wrapper
# 객체 검출 (person bbox + 배경 객체)
# ============================================================

import torch
import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DetectionResult:
    """단일 검출 결과"""
    label: str
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) normalized
    confidence: float


@dataclass
class GroundingDINOOutput:
    """Grounding DINO 전체 출력"""
    person_bbox: Optional[Tuple[float, float, float, float]]
    person_confidence: float
    background_objects: List[DetectionResult]
    image_size: Tuple[int, int]  # (width, height)


class GroundingDINOWrapper:
    """
    Grounding DINO 모델 래퍼

    Usage:
        wrapper = GroundingDINOWrapper(device="cuda")
        result = wrapper.detect(image, person_prompt="person",
                                bg_prompts=["window", "table"])
    """

    def __init__(
        self,
        model_id: str = "IDEA-Research/grounding-dino-base",
        box_threshold: float = 0.35,
        text_threshold: float = 0.25,
        device: str = "cuda"
    ):
        self.model_id = model_id
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        self.device = device
        self.model = None
        self.processor = None

    def load(self):
        """모델 로드"""
        try:
            # 방법 1: groundingdino-py 패키지 사용
            from groundingdino.util.inference import load_model, predict
            from groundingdino.util.inference import load_image as gd_load_image

            # 모델 경로 (사전 다운로드 필요)
            self.model = load_model(
                "groundingdino/config/GroundingDINO_SwinB_cfg.py",
                "weights/groundingdino_swinb_cogcoor.pth",
                device=self.device
            )
            self._use_native = True
            print(f"[GroundingDINO] Loaded native model on {self.device}")

        except ImportError:
            # 방법 2: HuggingFace transformers 사용
            from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

            self.processor = AutoProcessor.from_pretrained(self.model_id)
            self.model = AutoModelForZeroShotObjectDetection.from_pretrained(
                self.model_id
            ).to(self.device)
            self._use_native = False
            print(f"[GroundingDINO] Loaded HuggingFace model on {self.device}")

    def detect(
        self,
        image: Image.Image,
        person_prompt: str = "person",
        bg_prompts: Optional[List[str]] = None
    ) -> GroundingDINOOutput:
        """
        이미지에서 person과 배경 객체 검출

        Args:
            image: PIL Image
            person_prompt: person 검출 프롬프트
            bg_prompts: 배경 객체 프롬프트 리스트

        Returns:
            GroundingDINOOutput
        """
        if self.model is None:
            self.load()

        if bg_prompts is None:
            bg_prompts = []

        width, height = image.size

        # 모든 프롬프트 합치기
        all_prompts = [person_prompt] + bg_prompts
        text_prompt = " . ".join(all_prompts) + " ."

        if self._use_native:
            detections = self._detect_native(image, text_prompt)
        else:
            detections = self._detect_hf(image, text_prompt)

        # Person bbox 추출
        person_bbox = None
        person_confidence = 0.0
        background_objects = []

        for det in detections:
            if det.label.lower() in ["person", "man", "woman", "people"]:
                if det.confidence > person_confidence:
                    person_bbox = det.bbox
                    person_confidence = det.confidence
            else:
                background_objects.append(det)

        return GroundingDINOOutput(
            person_bbox=person_bbox,
            person_confidence=person_confidence,
            background_objects=background_objects,
            image_size=(width, height)
        )

    def _detect_native(self, image: Image.Image, text_prompt: str) -> List[DetectionResult]:
        """Native groundingdino 사용"""
        from groundingdino.util.inference import predict
        import groundingdino.datasets.transforms as T

        # 이미지 변환
        transform = T.Compose([
            T.RandomResize([800], max_size=1333),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        image_tensor, _ = transform(image, None)

        boxes, logits, phrases = predict(
            model=self.model,
            image=image_tensor,
            caption=text_prompt,
            box_threshold=self.box_threshold,
            text_threshold=self.text_threshold,
            device=self.device
        )

        results = []
        for box, logit, phrase in zip(boxes, logits, phrases):
            results.append(DetectionResult(
                label=phrase,
                bbox=tuple(box.tolist()),
                confidence=float(logit)
            ))

        return results

    def _detect_hf(self, image: Image.Image, text_prompt: str) -> List[DetectionResult]:
        """HuggingFace transformers 사용"""
        inputs = self.processor(
            images=image,
            text=text_prompt,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        results = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            box_threshold=self.box_threshold,
            text_threshold=self.text_threshold,
            target_sizes=[image.size[::-1]]  # (height, width)
        )[0]

        detections = []
        width, height = image.size

        for box, score, label in zip(
            results["boxes"],
            results["scores"],
            results["labels"]
        ):
            # Normalize bbox
            x1, y1, x2, y2 = box.tolist()
            normalized_bbox = (
                x1 / width,
                y1 / height,
                x2 / width,
                y2 / height
            )

            detections.append(DetectionResult(
                label=label,
                bbox=normalized_bbox,
                confidence=float(score)
            ))

        return detections


# ============================================================
# Quick Test
# ============================================================
if __name__ == "__main__":
    from PIL import Image

    # 테스트
    wrapper = GroundingDINOWrapper(device="cuda")

    # 테스트 이미지 로드
    test_image = Image.new("RGB", (640, 480), color="white")

    result = wrapper.detect(
        test_image,
        person_prompt="person",
        bg_prompts=["window", "table"]
    )

    print(f"Person bbox: {result.person_bbox}")
    print(f"Person confidence: {result.person_confidence}")
    print(f"Background objects: {len(result.background_objects)}")
