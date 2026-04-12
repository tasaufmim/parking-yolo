import json
import os
import time
from datetime import datetime
import numpy as np
import cv2

DATA_FILE = "rois.json"
DELAY_SECONDS = 15


class ROIManager:
    def __init__(self):
        self.slots: list[dict] = []
        self.slot_tracking: dict[str, dict] = {}
        self.captured_vehicles: dict[str, dict] = {}
        self.captured_plates: dict[str, dict] = {}
        self.last_statuses: list[dict] = []
        self.last_snapshot_error: str | None = None
        self.license_plate_detector = None
        self.plate_ocr_callback = None
        self.plate_ocr_instance = None
        self.history_manager = None
        self.on_ocr_complete = None
        self._init_license_plate_detector()
        self.load()

    def set_plate_ocr_callback(self, callback):
        """Set callback for async plate OCR."""
        self.plate_ocr_callback = callback

    def set_plate_ocr_instance(self, plate_ocr):
        """Set plate OCR instance for accessing results."""
        self.plate_ocr_instance = plate_ocr
    
    def set_history_manager(self, history_manager):
        """Set history manager for tracking parking events."""
        self.history_manager = history_manager
    
    def set_on_ocr_complete(self, callback):
        """Set callback to be called when OCR completes (success or fail)."""
        self.on_ocr_complete = callback

    def _init_license_plate_detector(self):
        """Initialize license plate detector."""
        try:
            from license_plate_detector import LicensePlateDetector
            self.license_plate_detector = LicensePlateDetector()
        except Exception:
            self.license_plate_detector = None

    def set_license_plate_detector(self, detector):
        """Set the license plate detector instance."""
        self.license_plate_detector = detector

    def _get_vehicle_snapshot_path(self) -> str:
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        path = os.path.join("logs", date_str, "snapshots", "vehicles")
        os.makedirs(path, exist_ok=True)
        return path

    def _get_plate_snapshot_path(self) -> str:
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        path = os.path.join("logs", date_str, "snapshots", "license_plates")
        os.makedirs(path, exist_ok=True)
        return path

    def capture_snapshot(
        self, frame: np.ndarray, slot_id: str, car_id: str, detection_bbox: list[int]
    ) -> tuple[bool, str]:
        """Capture snapshot of vehicle. Returns (success, error_message)."""
        capture_key = f"{slot_id}_{car_id}"

        if capture_key in self.captured_vehicles:
            return False, f"{car_id} already captured in {slot_id}"

        x1, y1, x2, y2 = detection_bbox
        pad = 10
        h, w = frame.shape[:2]
        x1_p = max(0, x1 - pad)
        y1_p = max(0, y1 - pad)
        x2_p = min(w, x2 + pad)
        y2_p = min(h, y2 + pad)

        cropped = frame[y1_p:y2_p, x1_p:x2_p]
        if cropped.size == 0:
            self.last_snapshot_error = f"Failed to crop {car_id}"
            return False, self.last_snapshot_error

        now = datetime.now()
        timestamp = now.strftime("%y%m%d_%H%M%S")
        filename = f"{timestamp}_{slot_id}_{car_id}.jpg"
        filepath = os.path.join(self._get_vehicle_snapshot_path(), filename)

        try:
            success = cv2.imwrite(filepath, cropped)
            if success:
                self.captured_vehicles[capture_key] = {
                    "filepath": filepath,
                    "captured_at": now.isoformat(),
                    "detection_bbox": detection_bbox,
                }
                self.last_snapshot_error = None
                return True, ""
            else:
                self.last_snapshot_error = f"Failed to save {car_id}"
                return False, self.last_snapshot_error
        except Exception as e:
            self.last_snapshot_error = f"Error saving {car_id}: {str(e)}"
            return False, self.last_snapshot_error

    def capture_license_plate(
        self, frame: np.ndarray, slot_id: str, car_id: str, detection_bbox: list[int]
    ) -> tuple[bool, str, np.ndarray | None]:
        """Capture license plate from vehicle. Returns (success, error_message, plate_image)."""
        if self.license_plate_detector is None:
            return False, "License plate detector not initialized", None

        capture_key = f"{slot_id}_{car_id}"
        if capture_key in self.captured_plates:
            return False, f"License plate already captured for {car_id} in {slot_id}", None

        x1, y1, x2, y2 = detection_bbox
        pad = 10
        h, w = frame.shape[:2]
        x1_p = max(0, x1 - pad)
        y1_p = max(0, y1 - pad)
        x2_p = min(w, x2 + pad)
        y2_p = min(h, y2 + pad)

        cropped_vehicle = frame[y1_p:y2_p, x1_p:x2_p]
        if cropped_vehicle.size == 0:
            return False, "Failed to crop vehicle for plate detection", None

        enhanced_plate, plate_bbox = self.license_plate_detector.get_best_plate(cropped_vehicle)
        if enhanced_plate is None:
            return False, "No license plate detected", None

        if plate_bbox:
            abs_x1 = x1_p + plate_bbox[0]
            abs_y1 = y1_p + plate_bbox[1]
            abs_x2 = x1_p + plate_bbox[2]
            abs_y2 = y1_p + plate_bbox[3]
            plate_bbox = [abs_x1, abs_y1, abs_x2, abs_y2]

        now = datetime.now()
        timestamp = now.strftime("%y%m%d_%H%M%S")
        filename = f"{timestamp}_{slot_id}_{car_id}_licenseplate.jpg"
        filepath = os.path.join(self._get_plate_snapshot_path(), filename)

        try:
            success = cv2.imwrite(filepath, enhanced_plate)
            if success:
                self.captured_plates[capture_key] = {
                    "filepath": filepath,
                    "captured_at": now.isoformat(),
                    "plate_bbox": plate_bbox,
                }
                return True, "", enhanced_plate
            else:
                return False, f"Failed to save license plate for {car_id}", None
        except Exception as e:
            return False, f"Error saving license plate: {str(e)}", None

    def get_snapshot_error(self) -> str | None:
        err = self.last_snapshot_error
        self.last_snapshot_error = None
        return err

    def is_already_captured(self, slot_id: str, car_id: str) -> bool:
        capture_key = f"{slot_id}_{car_id}"
        return capture_key in self.captured_vehicles

    def check_and_capture(
        self, frame: np.ndarray, detections: list[dict], current_statuses: list[dict]
    ) -> list[dict]:
        """Check for new confirmations and capture snapshots. Returns statuses with just_confirmed flag."""
        if not self.last_statuses:
            self.last_statuses = current_statuses
            return current_statuses

        current_dict = {s["id"]: s for s in current_statuses}
        last_dict = {s["id"]: s for s in self.last_statuses}

        for slot_id in current_dict:
            curr = current_dict[slot_id]
            last = last_dict.get(slot_id, {})

            was_confirmed = last.get("occupied", False) and not last.get("pending", False)
            is_confirmed = curr.get("occupied", False) and not curr.get("pending", False)

            curr["just_confirmed"] = False

            if is_confirmed and not was_confirmed:
                curr["just_confirmed"] = True
                car_id = curr.get("car_id")
                if car_id:
                    for det in detections:
                        if det.get("car_id") == car_id:
                            # Capture vehicle snapshot (for history photo)
                            success, error = self.capture_snapshot(
                                frame, slot_id, car_id, det["bbox"]
                            )
                            if success:
                                curr["snapshot_captured"] = True
                            
                            # Capture license plate
                            plate_success, plate_error, plate_image = self.capture_license_plate(
                                frame, slot_id, car_id, det["bbox"]
                            )
                            if plate_success:
                                curr["plate_captured"] = True
                                if self.plate_ocr_callback and plate_image is not None:
                                    now = datetime.now()
                                    filename = f"{now.strftime('%y%m%d_%H%M%S')}_{slot_id}_{car_id}_licenseplate.jpg"
                                    self.plate_ocr_callback(plate_image, slot_id, car_id, filename)
                            break
            
            # Handle slot becoming free
            if was_confirmed and not is_confirmed:
                last_car_id = last.get("car_id")
                # Check if history entry exists for this car/slot
                if last_car_id and self.history_manager:
                    existing = self.history_manager.get_by_car_id_slot(last_car_id, slot_id)
                    if not existing:
                        # No OCR completed - create fallback entry with N/A
                        capture_info = self.captured_vehicles.get(f"{slot_id}_{last_car_id}", {})
                        frame_path = capture_info.get("filepath")
                        self.history_manager.start_parking(slot_id, last_car_id, frame_path, None)
                    # End parking
                    self.history_manager.end_parking(slot_id, last_car_id)

        self.last_statuses = current_statuses
        return current_statuses

    def clear_captured(self):
        """Clear captured vehicle and plate tracking."""
        self.captured_vehicles = {}
        self.captured_plates = {}
        self.last_statuses = []

    def clear_all(self):
        self.slots = []
        self.slot_tracking = {}
        self.clear_captured()
        self.save()

    def add_slot(self, points: list[list[int]], slot_id: str | None = None) -> dict:
        if slot_id is None:
            slot_id = f"P{len(self.slots) + 1}"
        pts = np.array(points, dtype=np.int32)
        M = cv2.moments(pts)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
        slot = {"id": slot_id, "points": points, "centroid": [cx, cy]}
        self.slots.append(slot)
        self.slot_tracking[slot_id] = {
            "pending_start": None,
            "pending_state": None,
            "confirmed_state": False,
        }
        self.save()
        return slot

    def clear_all(self):
        self.slots = []
        self.slot_tracking = {}
        self.save()

    def get_all(self) -> list[dict]:
        return self.slots

    def get_polygons(self) -> list[tuple[str, np.ndarray]]:
        result = []
        for slot in self.slots:
            pts = np.array(slot["points"], dtype=np.int32)
            result.append((slot["id"], pts))
        return result

    def check_occupancy(self, detections: list[dict]) -> list[dict]:
        status = []
        current_time = time.time()

        for slot in self.slots:
            slot_id = slot["id"]
            sx, sy = slot["centroid"]

            current_occupied = False
            car_id = None
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                if x1 <= sx <= x2 and y1 <= sy <= y2:
                    current_occupied = True
                    car_id = det.get("car_id")
                    break

            tracking = self.slot_tracking.get(slot_id)
            if tracking is None:
                tracking = {
                    "pending_start": None,
                    "pending_state": None,
                    "confirmed_state": current_occupied,
                    "car_id": car_id,
                }
                self.slot_tracking[slot_id] = tracking
            else:
                tracking["car_id"] = car_id

            confirmed_state = tracking["confirmed_state"]
            pending_state = tracking["pending_state"]
            pending_start = tracking["pending_start"]
            confirmed_car_id = tracking.get("car_id")

            if current_occupied == confirmed_state:
                tracking["pending_start"] = None
                tracking["pending_state"] = None
            else:
                if tracking["pending_state"] is None:
                    tracking["pending_state"] = current_occupied
                    tracking["pending_start"] = current_time
                else:
                    if current_occupied != tracking["pending_state"]:
                        tracking["pending_state"] = current_occupied
                        tracking["pending_start"] = current_time

                if pending_start is not None:
                    elapsed = current_time - pending_start
                    if elapsed >= DELAY_SECONDS:
                        tracking["confirmed_state"] = tracking["pending_state"]
                        tracking["pending_state"] = None
                        tracking["pending_start"] = None

            final_occupied = confirmed_state
            final_car_id = confirmed_car_id
            if tracking["pending_state"] is not None:
                final_occupied = tracking["confirmed_state"]
                final_car_id = None

            remaining = 0.0
            if pending_start is not None:
                remaining = max(0, DELAY_SECONDS - (current_time - pending_start))

            status.append({
                "id": slot_id,
                "occupied": final_occupied,
                "car_id": final_car_id,
                "pending": pending_state is not None,
                "pending_state": pending_state,
                "remaining_seconds": remaining,
            })
        return status

    def draw_rois(self, frame, slot_statuses: list[dict] | None = None):
        for slot in self.slots:
            pts = np.array(slot["points"], dtype=np.int32)
            color = (255, 255, 0)
            label = slot["id"]

            if slot_statuses:
                status = next((s for s in slot_statuses if s["id"] == slot["id"]), None)
                if status:
                    if status.get("pending"):
                        if status["pending_state"]:
                            color = (0, 165, 255)
                        else:
                            color = (0, 255, 165)
                        label = slot["id"]
                    else:
                        color = (0, 0, 255) if status["occupied"] else (0, 255, 0)
                        label = f"{slot['id']}: {'OCCUPIED' if status['occupied'] else 'FREE'}"

            cv2.polylines(frame, [pts], True, color, 2)
            cx, cy = slot["centroid"]
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.putText(frame, label, (cx - 20, cy - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame

    def draw_plate_overlay(self, frame: np.ndarray, slot_statuses: list[dict] | None = None) -> np.ndarray:
        """Draw license plate text and bbox on frame."""
        if not slot_statuses:
            return frame
        
        for slot in self.slots:
            slot_id = slot["id"]
            status = next((s for s in slot_statuses if s["id"] == slot_id), None)
            
            if not status or not status.get("occupied"):
                continue
            
            car_id = status.get("car_id")
            if not car_id:
                continue
            
            capture_key = f"{slot_id}_{car_id}"
            plate_data = self.captured_plates.get(capture_key, {})
            plate_bbox = plate_data.get("plate_bbox")
            
            if not plate_bbox:
                continue
            
            x1, y1, x2, y2 = plate_bbox
            h, w = frame.shape[:2]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            
            plate_text = ""
            if self.plate_ocr_instance:
                plate_result = self.plate_ocr_instance.get_result(slot_id, car_id)
                plate_text = plate_result.get("plate_text", "")
            
            if plate_text and plate_text not in ["N/A", "Error", "Timeout", "processing"]:
                text_bg_y1 = max(0, y1 - 20)
                cv2.rectangle(frame, (x1, text_bg_y1), (x1 + len(plate_text) * 12, y1), (0, 255, 255), -1)
                cv2.putText(frame, plate_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        return frame

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.slots, f, indent=2)

    def load(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                self.slots = json.load(f)
        for slot in self.slots:
            slot_id = slot["id"]
            if slot_id not in self.slot_tracking:
                self.slot_tracking[slot_id] = {
                    "pending_start": None,
                    "pending_state": None,
                    "confirmed_state": False,
                }
