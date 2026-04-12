"""
License Plate Detector using YOLOv8
"""
import cv2
import numpy as np
import torch
from ultralytics import YOLO


class LicensePlateDetector:
    def __init__(self, model_path: str = "yolov8n-license-plate.pt", confidence: float = 0.5):
        self.model = YOLO(model_path)
        self.confidence = confidence
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

    def detect(self, cropped_vehicle: np.ndarray) -> list[dict]:
        """Detect license plates. Returns [{bbox, confidence}]"""
        results = self.model.predict(cropped_vehicle, conf=self.confidence, verbose=False)
        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                detections.append({"bbox": [x1, y1, x2, y2], "confidence": conf})
        return sorted(detections, key=lambda d: d["confidence"], reverse=True)

    def get_best_plate(self, cropped_vehicle: np.ndarray) -> tuple[np.ndarray | None, list[int] | None]:
        """Get enhanced plate crop. Returns (enhanced_plate, bbox) or (None, None)"""
        detections = self.detect(cropped_vehicle)
        if not detections:
            return None, None
        
        best = detections[0]
        x1, y1, x2, y2 = best["bbox"]
        pad = 2
        h, w = cropped_vehicle.shape[:2]
        x1_p, y1_p = max(0, x1 - pad), max(0, y1 - pad)
        x2_p, y2_p = min(w, x2 + pad), min(h, y2 + pad)
        
        plate_crop = cropped_vehicle[y1_p:y2_p, x1_p:x2_p]
        if plate_crop.size == 0:
            return None, None
        
        return self._enhance(plate_crop), best["bbox"]

    def _enhance(self, plate_crop: np.ndarray) -> np.ndarray:
        """CLAHE + 3x resize (keep color)"""
        if len(plate_crop.shape) == 3 and plate_crop.shape[2] == 3:
            lab = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced_lab = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(plate_crop)
        
        scale_factor = 3
        new_h, new_w = enhanced.shape[:2]
        enhanced = cv2.resize(enhanced, (new_w * scale_factor, new_h * scale_factor), interpolation=cv2.INTER_CUBIC)
        return enhanced