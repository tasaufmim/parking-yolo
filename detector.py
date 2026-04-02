import torch
import cv2
from ultralytics import YOLO
import numpy as np


class CarDetector:
    def __init__(self, confidence: float = 0.5):
        self.model = YOLO("yolov8m.pt")
        self.confidence = confidence
        self.vehicle_classes = [2, 5, 7]
        self.class_names = {2: "Car", 5: "Bus", 7: "Truck"}
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"
        print(f"YOLOv8 running on: {self.device}")

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Run detection on a frame. Returns list of {bbox, centroid, confidence}."""
        results = self.model.predict(
            frame,
            conf=self.confidence,
            classes=self.vehicle_classes,
            device=self.device,
            verbose=False,
        )
        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cls = int(box.cls[0])
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float(box.conf[0]),
                    "class": self.class_names.get(cls, f"cls_{cls}"),
                })
        return detections

    def draw_detections(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes on frame."""
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]
            label = f"{det['class']} {conf:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        return frame
