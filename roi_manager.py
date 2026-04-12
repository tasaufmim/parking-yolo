import json
import os
import time
import numpy as np
import cv2

DATA_FILE = "rois.json"
DELAY_SECONDS = 15


class ROIManager:
    def __init__(self):
        self.slots: list[dict] = []
        self.slot_tracking: dict[str, dict] = {}
        self.load()

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
