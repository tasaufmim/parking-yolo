import json
import os
import numpy as np
import cv2

DATA_FILE = "rois.json"


class ROIManager:
    def __init__(self):
        self.slots: list[dict] = []
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
        self.save()
        return slot

    def clear_all(self):
        self.slots = []
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
        """Check which slots are occupied — slot centroid inside car bbox."""
        status = []
        for slot in self.slots:
            sx, sy = slot["centroid"]
            occupied = False
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                if x1 <= sx <= x2 and y1 <= sy <= y2:
                    occupied = True
                    break
            status.append({"id": slot["id"], "occupied": occupied})
        return status

    def draw_rois(self, frame, slot_statuses: list[dict] | None = None):
        """Draw ROI polygons and centroids on frame."""
        for slot in self.slots:
            pts = np.array(slot["points"], dtype=np.int32)
            if slot_statuses:
                status = next((s for s in slot_statuses if s["id"] == slot["id"]), None)
                color = (0, 0, 255) if status and status["occupied"] else (0, 255, 0)
            else:
                color = (255, 255, 0)
            cv2.polylines(frame, [pts], True, color, 2)
            cx, cy = slot["centroid"]
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            label = slot["id"]
            if slot_statuses:
                status = next((s for s in slot_statuses if s["id"] == slot["id"]), None)
                if status:
                    label = f"{slot['id']}: {'OCCUPIED' if status['occupied'] else 'FREE'}"
            cv2.putText(frame, label, (cx - 20, cy - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.slots, f, indent=2)

    def load(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                self.slots = json.load(f)
