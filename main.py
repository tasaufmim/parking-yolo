import os
import uuid
import asyncio
import cv2
import numpy as np
import threading
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from detector import CarDetector
from video_processor import VideoProcessor
from roi_manager import ROIManager
from plate_ocr import PlateOCR
from history_manager import HistoryManager
from camera_manager import (
    add_camera, get_cameras, get_camera as db_get_camera,
    update_camera, delete_camera, toggle_enabled, is_full, MAX_CAMERAS
)

app = FastAPI(title="Parking Management MVP")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

history_manager = HistoryManager()
detector: CarDetector | None = None
plate_ocr = PlateOCR()

camera_processors: dict[str, dict] = {}
_stream_locks: dict[str, threading.Lock] = {}


def get_detector():
    global detector
    if detector is None:
        detector = CarDetector(confidence=0.8)
    return detector


class ROIRequest(BaseModel):
    points: list[list[int]]
    slot_id: str | None = None


class RTSPRequest(BaseModel):
    url: str


class CameraCreate(BaseModel):
    name: str
    rtsp_url: str


class CameraUpdate(BaseModel):
    name: str
    rtsp_url: str


class CameraEnable(BaseModel):
    enabled: bool


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    raise HTTPException(503, "Upload video is deprecated. Use camera streams.")


@app.post("/connect_rtsp")
async def connect_rtsp(req: RTSPRequest):
    raise HTTPException(503, "connect_rtsp is deprecated. Use POST /cameras/{id}/connect")


@app.post("/disconnect")
async def disconnect():
    raise HTTPException(503, "disconnect is deprecated. Use POST /cameras/{id}/disconnect")


@app.get("/video_feed")
async def video_feed():
    raise HTTPException(503, "video_feed is deprecated. Use /cameras/{id}/video_feed")


@app.get("/resolution")
async def resolution():
    raise HTTPException(503, "resolution is deprecated. Use /cameras/{id}/resolution")


@app.get("/snapshot")
async def snapshot():
    raise HTTPException(503, "snapshot is deprecated. Use /cameras/{id}/snapshot")


@app.get("/status")
async def get_status():
    raise HTTPException(503, "status is deprecated. Use /cameras/all_status")


@app.post("/roi")
async def add_roi(req: ROIRequest):
    raise HTTPException(503, "ROI is deprecated. Use /cameras/{id}/roi")


@app.delete("/roi")
async def clear_roi():
    raise HTTPException(503, "ROI is deprecated. Use /cameras/{id}/roi")


@app.get("/roi")
async def get_roi():
    raise HTTPException(503, "ROI is deprecated. Use /cameras/{id}/roi")


@app.get("/history")
async def get_history(page: int = 1, per_page: int = 100, status: str = None):
    return history_manager.get_history(page, per_page or 100, status)


@app.get("/history/{sl}")
async def get_history_detail(sl: int):
    entry = history_manager.get_by_sl(sl)
    if not entry:
        raise HTTPException(404, "Entry not found")
    return entry


@app.post("/history/{sl}/retry")
async def retry_ocr(sl: int):
    entry = history_manager.get_by_sl(sl)
    if not entry:
        raise HTTPException(404, "Entry not found")

    if not history_manager.can_retry(sl):
        raise HTTPException(400, "Retry not available for this entry")

    history_manager.update_retry_status(sl, "pending")

    try:
        image = history_manager.get_car_photo(sl)
        if image is None:
            history_manager.update_retry_status(sl, "failed", increment_count=True)
            raise HTTPException(400, "No car photo available")

        result = await plate_ocr.analyze_async(
            image,
            entry["slot_id"],
            entry["car_id"],
            entry.get("car_photo_path")
        )

        updated = history_manager.update_ocr_result(sl, result)
        history_manager.update_retry_status(sl, "success", increment_count=True)

        return updated
    except Exception as e:
        history_manager.update_retry_status(sl, "failed", increment_count=True)
        raise HTTPException(500, str(e))


@app.get("/history/export")
async def export_history():
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "SL", "Slot ID", "Car ID", "License Plate", "Plate Color",
        "Text Color", "Vehicle Type", "OCR Source", "Time Parked",
        "Time Left", "Duration (min)", "Status"
    ])

    data = history_manager.get_history(page=1, per_page=100000)
    for entry in data["entries"]:
        writer.writerow([
            entry["sl"],
            entry["slot_id"],
            entry["car_id"],
            entry.get("plate_number", "N/A"),
            entry.get("plate_color", "N/A"),
            entry.get("text_color", "N/A"),
            entry.get("vehicle_type", "N/A"),
            entry.get("ocr_source", "N/A"),
            entry.get("time_parked", "N/A"),
            entry.get("time_left", "N/A"),
            entry.get("duration_minutes", "N/A"),
            entry["status"]
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=parking_history.csv"}
    )


@app.delete("/history")
async def clear_history():
    history_manager.clear_history()
    return {"message": "History cleared"}


@app.get("/cameras")
async def list_cameras():
    cameras = get_cameras()
    full = is_full()
    result = []
    for cam in cameras:
        cp = camera_processors.get(cam["id"])
        connected = cp is not None and cp.get("connected", False)
        result.append({**cam, "stream_connected": connected})
    return {"cameras": result, "max_cameras": MAX_CAMERAS, "can_add": not full}


@app.post("/cameras")
async def create_camera(req: CameraCreate):
    if not req.name.strip():
        raise HTTPException(400, "Name is required")
    if not req.rtsp_url.strip():
        raise HTTPException(400, "RTSP URL is required")
    try:
        camera = add_camera(req.name.strip(), req.rtsp_url.strip())
        return {"message": "Camera added", "camera": camera}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/cameras/{cam_id}")
async def update_camera_endpoint(cam_id: str, req: CameraUpdate):
    if not req.name.strip():
        raise HTTPException(400, "Name is required")
    if not req.rtsp_url.strip():
        raise HTTPException(400, "RTSP URL is required")
    cam = update_camera(cam_id, req.name.strip(), req.rtsp_url.strip())
    if not cam:
        raise HTTPException(404, "Camera not found")
    return {"message": "Camera updated", "camera": cam}


@app.delete("/cameras/{cam_id}")
async def remove_camera(cam_id: str):
    if cam_id in camera_processors:
        _stop_camera(cam_id)
    deleted = delete_camera(cam_id)
    if not deleted:
        raise HTTPException(404, "Camera not found")
    return {"message": "Camera deleted"}


@app.patch("/cameras/{cam_id}/enable")
async def toggle_camera(cam_id: str, req: CameraEnable):
    cam = toggle_enabled(cam_id, req.enabled)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return {"message": "Camera updated", "camera": cam}


def _stop_camera(cam_id: str):
    cp = camera_processors.get(cam_id)
    if cp:
        cp["processor"].stop()
        del camera_processors[cam_id]
    if cam_id in _stream_locks:
        del _stream_locks[cam_id]


def _enrich_status(cam_id: str, statuses: list[dict]) -> list[dict]:
    enriched = []
    for s in statuses:
        slot_data = dict(s)
        if s.get("car_id"):
            plate_result = plate_ocr.get_result(f"{cam_id}_{s['id']}", s["car_id"])
            is_processing = plate_ocr.is_processing(f"{cam_id}_{s['id']}", s["car_id"])
            if is_processing:
                slot_data["plate_status"] = "processing"
            elif plate_result.get("plate_text") == "N/A" or plate_result.get("plate_text") in ["Error", "Timeout"]:
                slot_data["plate_status"] = "N/A"
            else:
                slot_data["plate_status"] = "ready"
            slot_data["plate_text"] = plate_result.get("plate_text", "N/A")
            slot_data["plate_color"] = plate_result.get("plate_color", "N/A")
            slot_data["text_color"] = plate_result.get("text_color", "N/A")
        else:
            slot_data["plate_status"] = "N/A"
            slot_data["plate_text"] = "N/A"
            slot_data["plate_color"] = "N/A"
            slot_data["text_color"] = "N/A"
        enriched.append(slot_data)
    return enriched


@app.post("/cameras/{cam_id}/connect")
async def connect_camera(cam_id: str):
    cam = db_get_camera(cam_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    if not cam["enabled"]:
        raise HTTPException(400, "Camera is disabled")
    if cam_id in camera_processors:
        cp = camera_processors[cam_id]
        if cp.get("connected"):
            return {"message": f"Already connected to {cam['name']}", "camera": {**cam, "stream_connected": True}}

    d = get_detector()
    roi_mgr = ROIManager(camera_id=cam_id)
    roi_mgr.set_history_manager(history_manager)
    processor = VideoProcessor(cam["rtsp_url"], d, roi_mgr)
    processor.set_plate_ocr(plate_ocr)
    try:
        processor.start()
    except ValueError as e:
        raise HTTPException(400, str(e))

    camera_processors[cam_id] = {
        "processor": processor,
        "roi_manager": roi_mgr,
        "connected": True,
        "name": cam["name"],
        "rtsp_url": cam["rtsp_url"],
    }
    return {"message": f"Connected to {cam['name']}", "camera": {**cam, "stream_connected": True}}


@app.post("/cameras/{cam_id}/disconnect")
async def disconnect_camera(cam_id: str):
    cam = db_get_camera(cam_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    if cam_id not in camera_processors:
        return {"message": f"{cam['name']} is not connected"}
    _stop_camera(cam_id)
    return {"message": f"Disconnected from {cam['name']}"}


@app.get("/cameras/{cam_id}/video_feed")
async def camera_video_feed(cam_id: str):
    if cam_id not in camera_processors:
        raise HTTPException(400, "Camera not connected")

    if cam_id not in _stream_locks:
        _stream_locks[cam_id] = threading.Lock()

    lock = _stream_locks[cam_id]
    with lock:
        cp = camera_processors[cam_id]
        return StreamingResponse(
            cp["processor"].generate_mjpeg(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )


@app.get("/cameras/{cam_id}/resolution")
async def camera_resolution(cam_id: str):
    if cam_id not in camera_processors:
        raise HTTPException(400, "Camera not connected")
    cp = camera_processors[cam_id]
    return {"width": cp["processor"].frame_width, "height": cp["processor"].frame_height}


@app.get("/cameras/{cam_id}/snapshot")
async def camera_snapshot(cam_id: str):
    if cam_id not in camera_processors:
        raise HTTPException(400, "Camera not connected")
    cp = camera_processors[cam_id]
    frame = cp["processor"].get_snapshot()
    if frame is None:
        raise HTTPException(500, "Cannot read frame")
    _, buffer = cv2.imencode(".jpg", frame)
    return StreamingResponse(
        iter([buffer.tobytes()]),
        media_type="image/jpeg",
    )


@app.get("/cameras/{cam_id}/status")
async def camera_status(cam_id: str):
    if cam_id not in camera_processors:
        return {
            "slots": [], "total": 0, "occupied": 0, "free": 0,
            "detected": 0, "connected": False, "cam_id": cam_id,
            "name": None, "snapshot_error": None
        }
    cp = camera_processors[cam_id]
    processor = cp["processor"]
    statuses = processor.slot_statuses
    occupied = sum(1 for s in statuses if s["occupied"])
    detected = len(processor.detections) if processor.detections else 0
    snapshot_error = processor.get_snapshot_error()

    return {
        "slots": _enrich_status(cam_id, statuses),
        "total": len(statuses),
        "occupied": occupied,
        "free": len(statuses) - occupied,
        "detected": detected,
        "connected": cp["connected"],
        "cam_id": cam_id,
        "name": cp["name"],
        "snapshot_error": snapshot_error,
    }


@app.get("/cameras/all_status")
async def all_camera_status():
    cameras = get_cameras()
    result = []
    for cam in cameras:
        if cam["id"] in camera_processors:
            cp = camera_processors[cam["id"]]
            processor = cp["processor"]
            statuses = processor.slot_statuses
            occupied = sum(1 for s in statuses if s["occupied"])
            detected = len(processor.detections) if processor.detections else 0
            result.append({
                "cam_id": cam["id"],
                "name": cam["name"],
                "connected": cp["connected"],
                "slots": _enrich_status(cam["id"], statuses),
                "total": len(statuses),
                "occupied": occupied,
                "free": len(statuses) - occupied,
                "detected": detected,
                "snapshot_error": processor.get_snapshot_error(),
            })
        else:
            result.append({
                "cam_id": cam["id"],
                "name": cam["name"],
                "connected": False,
                "slots": [],
                "total": 0,
                "occupied": 0,
                "free": 0,
                "detected": 0,
                "snapshot_error": None,
            })
    return {"cameras": result}


@app.post("/cameras/{cam_id}/roi")
async def add_camera_roi(cam_id: str, req: ROIRequest):
    if cam_id not in camera_processors:
        raise HTTPException(400, "Camera not connected")
    if len(req.points) < 3:
        raise HTTPException(400, "Need at least 3 points for a polygon")
    roi_mgr = camera_processors[cam_id]["roi_manager"]
    slot = roi_mgr.add_slot(req.points, req.slot_id)
    return {"message": "ROI added", "slot": slot}


@app.delete("/cameras/{cam_id}/roi")
async def clear_camera_roi(cam_id: str):
    if cam_id not in camera_processors:
        raise HTTPException(400, "Camera not connected")
    roi_mgr = camera_processors[cam_id]["roi_manager"]
    roi_mgr.clear_all()
    return {"message": "All ROIs cleared"}


@app.get("/cameras/{cam_id}/roi")
async def get_camera_roi(cam_id: str):
    if cam_id not in camera_processors:
        raise HTTPException(400, "Camera not connected")
    roi_mgr = camera_processors[cam_id]["roi_manager"]
    return {"slots": roi_mgr.get_all()}


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/logs", StaticFiles(directory="logs"), name="logs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)