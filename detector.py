import torch
import cv2
import time
from datetime import datetime
from ultralytics import YOLO
import numpy as np


def enhance_frame(frame: np.ndarray) -> np.ndarray:
    """Enhance frame for better detection (CLAHE + brightness)."""
    if len(frame.shape) == 3 and frame.shape[2] == 3:
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        l = np.clip(l * 1.15, 0, 255).astype(np.uint8)
        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    return frame


class LicensePlateDetector:
    def __init__(self, confidence: float = 0.5):
        self.model = YOLO("yolov8n-license-plate.pt")
        self.confidence = confidence
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"
        print(f"License Plate Detection running on: {self.device}")

    def detect(self, cropped_vehicle: np.ndarray) -> list[dict]:
        """Detect license plates in cropped vehicle image. Returns list of {bbox, confidence}."""
        results = self.model.predict(
            cropped_vehicle,
            conf=self.confidence,
            verbose=False,
        )
        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                })
        return detections

    def get_best_plate(self, cropped_vehicle: np.ndarray) -> tuple[np.ndarray | None, list[int] | None]:
        """Get the best license plate crop and bbox. Returns (enhanced_plate, bbox) or (None, None)."""
        detections = self.detect(cropped_vehicle)
        if not detections:
            return None, None
        
        best = max(detections, key=lambda d: d["confidence"])
        x1, y1, x2, y2 = best["bbox"]
        
        pad = 2
        h, w = cropped_vehicle.shape[:2]
        x1_p = max(0, x1 - pad)
        y1_p = max(0, y1 - pad)
        x2_p = min(w, x2 + pad)
        y2_p = min(h, y2 + pad)
        
        plate_crop = cropped_vehicle[y1_p:y2_p, x1_p:x2_p]
        if plate_crop.size == 0:
            return None, None
        
        enhanced = self.enhance_plate(plate_crop)
        return enhanced, best["bbox"]

    def enhance_plate(self, plate_crop: np.ndarray) -> np.ndarray:
        """Enhance license plate image for better readability while preserving color."""
        if len(plate_crop.shape) == 3 and plate_crop.shape[2] == 3:
            lab = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        else:
            enhanced = plate_crop
        
        scale_factor = 3
        new_h, new_w = enhanced.shape[:2] * scale_factor
        enhanced = cv2.resize(enhanced, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        return enhanced


class CarDetector:
    def __init__(self, confidence: float = 0.9, use_enhancement: bool = True):
        self.model = YOLO("yolov8m.pt")
        self.confidence = confidence
        self.use_enhancement = use_enhancement
        self.vehicle_classes = [2, 5, 7]
        self.class_names = {2: "Car", 5: "Bus", 7: "Truck"}
        self.car_counters = {2: 0, 5: 0, 7: 0}
        self.track_data = {}
        self.track_timeout = 60
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"
        print(f"YOLOv8 running on: {self.device}")

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Run tracking on a frame. Returns list of {bbox, confidence, class, car_id, track_id}."""
        if self.use_enhancement:
            original_frame = frame
            frame = enhance_frame(frame)
        
        results = self.model.track(
            frame,
            conf=self.confidence,
            classes=self.vehicle_classes,
            device=self.device,
            persist=True,
            verbose=False,
        )
        detections = []
        current_time = time.time()
        current_date = datetime.now().strftime("%y%m%d")
        active_track_ids = set()

        for r in results:
            if r.boxes is None or r.boxes.id is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                track_id = int(box.id[0]) if box.id is not None else None
                car_label = self.class_names.get(cls, f"cls_{cls}")
                car_label_upper = car_label.upper()

                if track_id is not None:
                    active_track_ids.add(track_id)
                    if track_id not in self.track_data:
                        self.car_counters[cls] += 1
                        self.track_data[track_id] = {
                            "class": cls,
                            "car_label": car_label,
                            "car_label_upper": car_label_upper,
                            "counter": self.car_counters[cls],
                            "first_seen_date": current_date,
                            "last_seen": current_time,
                        }
                    else:
                        self.track_data[track_id]["last_seen"] = current_time

                    track_info = self.track_data[track_id]
                    car_id = f"{track_info['car_label_upper']}{track_info['first_seen_date']}{track_info['counter']:03d}"
                else:
                    self.car_counters[cls] += 1
                    car_id = f"{car_label_upper}{current_date}{self.car_counters[cls]:03d}"

                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class": car_label,
                    "car_id": car_id,
                    "track_id": track_id,
                })

        for tid in list(self.track_data.keys()):
            if tid not in active_track_ids:
                elapsed = current_time - self.track_data[tid]["last_seen"]
                if elapsed > self.track_timeout:
                    del self.track_data[tid]

        return detections

    def reset_tracking(self):
        """Reset tracking for new video."""
        self.car_counters = {2: 0, 5: 0, 7: 0}
        self.track_data = {}

    def clear_vehicles(self):
        """Clear all vehicle tracking data."""
        self.car_counters = {2: 0, 5: 0, 7: 0}
        self.track_data = {}

    def draw_detections(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes on frame."""
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]
            car_id = det.get("car_id", det["class"])
            label = f"{car_id} {conf:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        return frame
