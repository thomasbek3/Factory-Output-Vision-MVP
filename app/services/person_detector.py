from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PersonDetection:
    x: int
    y: int
    w: int
    h: int
    confidence: float


def point_in_polygon(point: tuple[int, int], polygon: list[tuple[int, int]]) -> bool:
    if len(polygon) < 3:
        return False
    return cv2.pointPolygonTest(np.array(polygon, dtype=np.int32), point, False) >= 0


class PersonDetector:
    def __init__(self, confidence_threshold: float = 0.5) -> None:
        from ultralytics import YOLO

        self._model = YOLO("yolov8n.pt")
        self._confidence_threshold = confidence_threshold

    def detect_people(self, frame: np.ndarray) -> list[PersonDetection]:
        results = self._model.predict(
            source=frame,
            conf=self._confidence_threshold,
            classes=[0],
            device="cpu",
            verbose=False,
        )
        detections: list[PersonDetection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                detections.append(
                    PersonDetection(
                        x=int(x1),
                        y=int(y1),
                        w=max(0, int(x2 - x1)),
                        h=max(0, int(y2 - y1)),
                        confidence=conf,
                    )
                )
        return detections
