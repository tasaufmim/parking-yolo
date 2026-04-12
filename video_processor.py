import cv2
import time
import numpy as np
from detector import CarDetector
from roi_manager import ROIManager


class VideoProcessor:
    def __init__(self, source: str, detector: CarDetector, roi_manager: ROIManager):
        self.source = source
        self.is_rtsp = source.startswith(("rtsp://", "rtmp://"))
        self.detector = detector
        self.roi_manager = roi_manager
        self.cap = None
        self.running = False
        self.connected = False
        self.slot_statuses: list[dict] = []
        self.detections: list[dict] = []
        self.frame_width = 0
        self.frame_height = 0

    def start(self):
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise ValueError(f"Cannot open source: {self.source}")
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.detector.reset_tracking()
        self.connected = True
        self.running = True

    def stop(self):
        self.running = False
        self.connected = False
        self.detector.reset_tracking()
        if self.cap:
            self.cap.release()
            self.cap = None

    def reconnect(self):
        """Auto-reconnect for RTSP streams."""
        if not self.is_rtsp or not self.running:
            return False
        print(f"Reconnecting to {self.source}...")
        if self.cap:
            self.cap.release()
        time.sleep(3)
        self.cap = cv2.VideoCapture(self.source)
        if self.cap.isOpened():
            self.connected = True
            print("Reconnected successfully")
            return True
        else:
            self.connected = False
            print("Reconnection failed")
            return False

    def get_frame(self) -> np.ndarray | None:
        if not self.cap or not self.running:
            return None

        # For RTSP, try reconnect if disconnected
        if self.is_rtsp and not self.connected:
            if not self.reconnect():
                return None

        ret, frame = self.cap.read()

        if not ret:
            if self.is_rtsp:
                # RTSP disconnected - attempt reconnect
                self.connected = False
                self.reconnect()
                return None
            else:
                # File ended - loop back to start
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    return None
                return frame

        self.connected = True
        return frame

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict]]:
        self.detections = self.detector.detect(frame)
        self.slot_statuses = self.roi_manager.check_occupancy(self.detections)
        frame = self.detector.draw_detections(frame, self.detections)
        frame = self.roi_manager.draw_rois(frame, self.slot_statuses)
        return frame, self.slot_statuses

    def get_snapshot(self) -> np.ndarray | None:
        if not self.cap:
            return None
        if self.is_rtsp:
            # For RTSP, just read current frame
            ret, frame = self.cap.read()
            if ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return frame if ret else None
        else:
            # For file, go to first frame
            pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            return frame if ret else None

    def generate_mjpeg(self):
        """Generator that yields MJPEG frames with frame skip."""
        frame_time = 1 / 15  # Target 15 FPS processing
        last_process_time = time.time()

        while self.running:
            # Frame skip: drop frames if processing is too slow
            elapsed = time.time() - last_process_time
            if elapsed < frame_time:
                # Read and discard frames to keep up with stream
                while elapsed < frame_time:
                    frame = self.get_frame()
                    if frame is None:
                        break
                    elapsed = time.time() - last_process_time
                    time.sleep(0.001)

            frame = self.get_frame()
            if frame is None:
                if self.is_rtsp:
                    # Show placeholder for RTSP while reconnecting
                    placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(
                        placeholder, "Reconnecting...", (180, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
                    )
                    _, buffer = cv2.imencode(".jpg", placeholder)
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + buffer.tobytes() + b"\r\n"
                    )
                    time.sleep(1)
                    continue
                else:
                    break

            last_process_time = time.time()
            frame, statuses = self.process_frame(frame)
            _, buffer = cv2.imencode(".jpg", frame)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes() + b"\r\n"
            )
