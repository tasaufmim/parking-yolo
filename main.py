import os
import uuid
import asyncio
import cv2
import numpy as np
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
from camera_manager import add_camera, get_cameras, get_camera, update_camera, delete_camera, toggle_enabled, is_full, MAX_CAMERAS

app = FastAPI(title="Parking Management MVP")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

roi_manager = ROIManager()
history_manager = HistoryManager()
detector: CarDetector | None = None
processor: VideoProcessor | None = None
current_video_path: str | None = None

plate_ocr = PlateOCR()
bg_tasks = []

roi_manager.set_history_manager(history_manager)


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


def get_detector():
    global detector
    if detector is None:
        detector = CarDetector(confidence=0.8)
    return detector


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    global processor, current_video_path
    allowed = {".mp4", ".avi", ".mov", ".mkv"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported format. Use: {', '.join(allowed)}")

    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    if processor:
        processor.stop()

    current_video_path = path
    d = get_detector()
    processor = VideoProcessor(path, d, roi_manager)
    processor.set_plate_ocr(plate_ocr)
    processor.start()

    return {"message": "Video uploaded", "filename": filename, "source": "file"}


@app.post("/connect_rtsp")
async def connect_rtsp(req: RTSPRequest):
    global processor
    if processor:
        processor.stop()
    d = get_detector()
    try:
        processor = VideoProcessor(req.url, d, roi_manager)
        processor.set_plate_ocr(plate_ocr)
        processor.start()
        return {"message": "Connected to RTSP stream", "source": "rtsp"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/disconnect")
async def disconnect():
    global processor
    if processor:
        processor.stop()
        processor = None
    return {"message": "Disconnected"}


@app.get("/video_feed")
async def video_feed():
    if not processor:
        raise HTTPException(400, "No video uploaded")
    return StreamingResponse(
        processor.generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/resolution")
async def resolution():
    if not processor:
        raise HTTPException(400, "No video uploaded")
    return {"width": processor.frame_width, "height": processor.frame_height}


@app.get("/snapshot")
async def snapshot():
    if not processor:
        raise HTTPException(400, "No video uploaded")
    frame = processor.get_snapshot()
    if frame is None:
        raise HTTPException(500, "Cannot read frame")
    _, buffer = cv2.imencode(".jpg", frame)
    return StreamingResponse(
        iter([buffer.tobytes()]),
        media_type="image/jpeg",
    )


@app.post("/roi")
async def add_roi(req: ROIRequest):
    if len(req.points) < 3:
        raise HTTPException(400, "Need at least 3 points for a polygon")
    slot = roi_manager.add_slot(req.points, req.slot_id)
    return {"message": "ROI added", "slot": slot}


@app.delete("/roi")
async def clear_roi():
    roi_manager.clear_all()
    return {"message": "All ROIs cleared"}


@app.get("/roi")
async def get_roi():
    return {"slots": roi_manager.get_all()}


@app.get("/status")
async def get_status():
    if not processor:
        return {"slots": [], "total": 0, "occupied": 0, "free": 0, "detected": 0, "connected": False, "source": None, "snapshot_error": None}
    statuses = processor.slot_statuses
    occupied = sum(1 for s in statuses if s["occupied"])
    detected = len(processor.detections) if processor.detections else 0
    snapshot_error = processor.get_snapshot_error()
    
    enriched_statuses = []
    for s in statuses:
        slot_data = dict(s)
        if s.get("car_id"):
            plate_result = plate_ocr.get_result(s["id"], s["car_id"])
            is_processing = plate_ocr.is_processing(s["id"], s["car_id"])
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
        enriched_statuses.append(slot_data)
    
    return {
        "slots": enriched_statuses,
        "total": len(statuses),
        "occupied": occupied,
        "free": len(statuses) - occupied,
        "detected": detected,
        "connected": processor.connected,
        "source": "rtsp" if processor.is_rtsp else "file",
        "snapshot_error": snapshot_error,
    }


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
    from fastapi.responses import StreamingResponse
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
    return {"cameras": cameras, "max_cameras": MAX_CAMERAS, "can_add": not full}


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
    camera = update_camera(cam_id, req.name.strip(), req.rtsp_url.strip())
    if not camera:
        raise HTTPException(404, "Camera not found")
    return {"message": "Camera updated", "camera": camera}


@app.delete("/cameras/{cam_id}")
async def remove_camera(cam_id: str):
    deleted = delete_camera(cam_id)
    if not deleted:
        raise HTTPException(404, "Camera not found")
    return {"message": "Camera deleted"}


@app.patch("/cameras/{cam_id}/enable")
async def toggle_camera(cam_id: str, req: CameraEnable):
    camera = toggle_enabled(cam_id, req.enabled)
    if not camera:
        raise HTTPException(404, "Camera not found")
    return {"message": "Camera updated", "camera": camera}


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/logs", StaticFiles(directory="logs"), name="logs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
