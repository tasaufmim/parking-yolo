import cv2
import time
import threading
import asyncio
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
        self.plate_ocr = None
        self._cap_lock = threading.Lock()
        self._generator_active = False

    def set_plate_ocr(self, plate_ocr):
        self.plate_ocr = plate_ocr
        if self.roi_manager:
            self.roi_manager.set_plate_ocr_instance(plate_ocr)
            self.roi_manager.set_plate_ocr_callback(
                lambda img, sid, cid, f: self._queue_ocr(img, sid, cid, f)
            )
            self.roi_manager.set_on_ocr_complete(
                lambda sid, cid, result: self._on_ocr_complete(sid, cid, result)
            )

    def _on_ocr_complete(self, slot_id, car_id, ocr_result):
        if self.roi_manager and self.roi_manager.history_manager:
            frame_path = self.roi_manager.last_capture_path
            self.roi_manager.history_manager.start_parking(slot_id, car_id, frame_path, ocr_result)

    def _queue_ocr(self, plate_image, slot_id, car_id, image_filename):
        if self.plate_ocr and plate_image is not None:
            thread = threading.Thread(
                target=self._run_async_ocr,
                args=(plate_image, slot_id, car_id, image_filename)
            )
            thread.daemon = True
            thread.start()

    def _run_async_ocr(self, plate_image, slot_id, car_id, image_filename):
        try:
            result = asyncio.run(
                self.plate_ocr.analyze_async(plate_image, slot_id, car_id, image_filename)
            )
            if self.roi_manager and hasattr(self.roi_manager, 'on_ocr_complete') and self.roi_manager.on_ocr_complete:
                self.roi_manager.on_ocr_complete(slot_id, car_id, result)
        except Exception as e:
            print(f"OCR error: {e}")
            if self.roi_manager and hasattr(self.roi_manager, 'on_ocr_complete') and self.roi_manager.on_ocr_complete:
                error_result = {
                    "plate_text": "N/A",
                    "plate_color": "N/A",
                    "text_color": "N/A",
                    "source": "error"
                }
                self.roi_manager.on_ocr_complete(slot_id, car_id, error_result)

    def start(self):
        with self._cap_lock:
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                raise ValueError(f"Cannot open source: {self.source}")
            self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.detector.reset_tracking()
            self.roi_manager.clear_captured()
            self.connected = True
            self.running = True

    def stop(self):
        with self._cap_lock:
            self.running = False
            self.connected = False
            self.detector.reset_tracking()
            if self.cap:
                self.cap.release()
                self.cap = None

    def reconnect(self):
        if not self.is_rtsp or not self.running:
            return False
        print(f"Reconnecting to {self.source}...")
        with self._cap_lock:
            if self.cap:
                self.cap.release()
            time.sleep(3)
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            if self.cap.isOpened():
                self.connected = True
                print("Reconnected successfully")
                return True
            else:
                self.connected = False
                print("Reconnection failed")
                return False

    def get_frame(self) -> np.ndarray | None:
        with self._cap_lock:
            if not self.cap or not self.running:
                return None

            if self.is_rtsp and not self.connected:
                if not self._unsafe_reconnect():
                    return None

            ret, frame = self.cap.read()

            if not ret:
                if self.is_rtsp:
                    self.connected = False
                    self._unsafe_reconnect()
                    return None
                else:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                    if not ret:
                        return None
                    return frame

            self.connected = True
            return frame

    def _unsafe_reconnect(self) -> bool:
        if not self.is_rtsp or not self.running:
            return False
        print(f"Reconnecting to {self.source}...")
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        time.sleep(3)
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        if self.cap.isOpened():
            self.connected = True
            print("Reconnected successfully")
            return True
        else:
            self.connected = False
            print("Reconnection failed")
            return False

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict]]:
        self.detections = self.detector.detect(frame)
        raw_statuses = self.roi_manager.check_occupancy(self.detections)
        self.slot_statuses = self.roi_manager.check_and_capture(frame, self.detections, raw_statuses)
        frame = self.detector.draw_detections(frame, self.detections)
        frame = self.roi_manager.draw_rois(frame, self.slot_statuses)
        frame = self.roi_manager.draw_plate_overlay(frame, self.slot_statuses)
        return frame, self.slot_statuses

    def get_snapshot(self) -> np.ndarray | None:
        with self._cap_lock:
            if not self.cap:
                return None
            if self.is_rtsp:
                ret, frame = self.cap.read()
                if ret:
                    try:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    except Exception:
                        pass
                return frame if ret else None
            else:
                pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                return frame if ret else None

    def get_snapshot_error(self) -> str | None:
        return self.roi_manager.get_snapshot_error()

    def generate_mjpeg(self):
        self._generator_active = True
        try:
            frame_time = 1 / 15
            last_process_time = time.time()

            while self.running:
                elapsed = time.time() - last_process_time
                if elapsed < frame_time:
                    while elapsed < frame_time:
                        frame = self.get_frame()
                        if frame is None:
                            break
                        elapsed = time.time() - last_process_time
                        time.sleep(0.001)

                frame = self.get_frame()
                if frame is None:
                    if self.is_rtsp:
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
        finally:
            self._generator_active = False