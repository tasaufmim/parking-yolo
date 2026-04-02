import os
import uuid
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from detector import CarDetector
from video_processor import VideoProcessor
from roi_manager import ROIManager

app = FastAPI(title="Parking Management MVP")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

roi_manager = ROIManager()
detector: CarDetector | None = None
processor: VideoProcessor | None = None
current_video_path: str | None = None


class ROIRequest(BaseModel):
    points: list[list[int]]
    slot_id: str | None = None


class RTSPRequest(BaseModel):
    url: str


def get_detector():
    global detector
    if detector is None:
        detector = CarDetector(confidence=0.5)
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
        return {"slots": [], "total": 0, "occupied": 0, "free": 0, "connected": False, "source": None}
    statuses = processor.slot_statuses
    occupied = sum(1 for s in statuses if s["occupied"])
    return {
        "slots": statuses,
        "total": len(statuses),
        "occupied": occupied,
        "free": len(statuses) - occupied,
        "connected": processor.connected,
        "source": "rtsp" if processor.is_rtsp else "file",
    }


app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
