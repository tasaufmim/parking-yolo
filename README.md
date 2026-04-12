# Parking YOLO

<div align="center">

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.124.4-009.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.1-61DAFB.svg)](https://react.dev)

**Smart Parking Management System with Real-time Vehicle & License Plate Detection**

</div>

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Usage Guide](#usage-guide)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [License](#license)

---

## Features

### 🔍 Real-time Vehicle Detection
- Uses **YOLOv8m** for detecting vehicles (Car, Bus, Truck)
- Object tracking with unique vehicle IDs
- Confidence-based detection with configurable threshold

### 🪪 License Plate Recognition
- **YOLOv8n** for license plate detection
- Dual OCR engine:
  - **OpenAI GPT-4o Vision API** (primary) - Advanced text understanding
  - **PaddleOCR** (fallback) - Local offline recognition
- Indian license plate format validation

### 📹 Video Stream Support
- **Video file upload**: MP4, AVI, MOV, MKV
- **RTSP live stream**: Real-time camera feeds
- Automatic reconnection for RTSP streams

### 🅿️ Parking Slot Management
- ROI (Region of Interest) based detection
- Polygon-based parking slot drawing
- 15-second confirmation delay for occupancy
- Visual status indicators (Free/Occupied/Pending)

### 📊 Parking History
- SQLite database for persistence
- Vehicle type classification by plate color
- Retry failed OCR attempts
- CSV export functionality

### 🖥️ Web Interface
- React 19 + Ant Design 5
- Real-time status updates
- Manual ROI drawing
- History panel with search & pagination

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI 0.124.4, uvicorn 0.38.0 |
| **ML/AI** | Ultralytics YOLOv8 8.3.245, OpenAI Vision API, PaddleOCR |
| **Frontend** | React 19.1, Ant Design 5.25.2, Vite 6.3.5 |
| **Database** | SQLite |
| **Image Processing** | OpenCV 4.12.0 (headless) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│   VideoPlayer | StatusPanel | ROIControls | HistoryPanel         │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                    FastAPI Backend                        │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ VideoProc │  │ ROI Manager│  │  History  │ │
│  └────┬─────┘  └────┬─────┘  └────┬────���┘ │
│       │              │              │         │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼────┐ │
│  │CarDetect│  │PlateDet │  │  SQLite │ │
│  │ YOLOv8m │  │YOLOv8n-LP│  │   DB   │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
      ┌──────────────────────┼──────────────────────┐
      │                      │                      │
┌─────▼─────┐  ┌──────────▼──────────┐  ┌────────▼────────┐
│ Video/File│  │  RTSP Stream      │  │ OpenAI API   │
└──────────┘  └─────────────────┘  │ PaddleOCR  │
                                 └───────────┘
```

---

## Prerequisites

### 1. Python Version
```bash
Python 3.11+
```

### 2. Required Model Files

Download and place these model files in the project root:

| Model File | Purpose | Size |
|-----------|---------|------|
| `yolov8m.pt` | Vehicle detection (YOLOv8 Medium) | ~50MB |
| `yolov8n-license-plate.pt` | License plate detection | ~6MB |

**Download from Ultralytics:**
```bash
# YOLOv8m for vehicles
wget https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt

# YOLOv8n for license plates
# (Download from your trained model or Ultralytics hub)
```

### 3. OpenAI API Key (Optional)
- For GPT-4o Vision OCR
- Set via `OPENAI_API_KEY` in `.env`
- If not set, PaddleOCR fallback will be used

---

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-repo/parking-yolo.git
cd parking-yolo
```

### 2. Create Virtual Environment (Recommended)
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows
```

### 3. Install Dependencies
```bash
pip3 install -r requirements.txt
```

**Installed Packages:**
```
fastapi==0.124.4
uvicorn==0.38.0
ultralytics==8.3.245
opencv-python-headless==4.12.0.88
python-multipart==0.0.21
numpy==2.2.6
aiohttp==3.13.5
python-dotenv==1.2.1
```

### 4. Install Frontend Dependencies
```bash
cd frontend
npm install
```

---

## Running the Application

### Start the Backend
```bash
python3 main.py
```

The server will start on `http://localhost:8000`

### Start the Frontend (Development)
```bash
cd frontend
npm run dev
```

Then open `http://localhost:5173` (or the port shown in terminal)

---

## Usage Guide

### Step 1: Access the Application

Open your browser and navigate to:
```
http://localhost:8000
```

You will see the main interface with three tabs:
- **Upload Video** - For uploading video files
- **RTSP Live Stream** - For connecting to camera streams
- **History** - For viewing parking history

### Step 2: Connect Video Source

#### Option A: Upload Video File
1. Click **Upload Video** tab
2. Drag & drop or click to select a video file
3. Supported formats: MP4, AVI, MOV, MKV
4. Wait for processing to start

#### Option B: RTSP Stream
1. Click **RTSP Live Stream** tab
2. Enter your RTSP URL (e.g., `rtsp://camera-ip:554/stream`)
3. Click **Connect**
4. Wait for connection status

### Step 3: Define Parking Slots (ROI)

#### Manual Drawing
1. Click **Draw** button in the controls panel
2. Click on the video to place corner points (minimum 3 points)
3. Click **Save** to create the slot
4. Repeat for additional slots

#### Slot Management
- **Slot Count**: Set number of slots to generate automatically
- **Generate**: Auto-generate evenly spaced slots
- **Clear**: Remove all slots

### Step 4: Monitor Status

The status panel shows:
- **Total Slots**: Total configured
- **Free**: Available spots
- **Occupied**: Taken spots
- **Detected**: Vehicles detected

### Step 5: View History

1. Click the **History** tab (third tab in the header)
2. View all parking transactions
3. Use search filters:
   - By status (active/completed)
   - By date range
4. **Export**: Download CSV report
5. **Retry OCR**: Retry failed plate recognition

### Step 6: OCR Retry

If OCR failed for a vehicle:

1. Go to **History** tab
2. Find the entry with failed OCR
3. Click **Retry** button
4. System will re-process the license plate

---

## API Reference

### Video Endpoints

| Method | Endpoint | Description |
|--------|---------|------------|
| `POST` | `/upload` | Upload video file |
| `POST` | `/connect_rtsp` | Connect to RTSP stream |
| `POST` | `/disconnect` | Disconnect current stream |
| `GET` | `/video_feed` | MJPEG video stream |
| `GET` | `/resolution` | Get video resolution |
| `GET` | `/snapshot` | Get current frame |

### ROI Endpoints

| Method | Endpoint | Description |
|--------|---------|------------|
| `GET` | `/roi` | Get all parking slots |
| `POST` | `/roi` | Add new parking slot |
| `DELETE` | `/roi` | Clear all slots |

### Status Endpoints

| Method | Endpoint | Description |
|--------|---------|------------|
| `GET` | `/status` | Get slot occupancy status |

### History Endpoints

| Method | Endpoint | Description |
|--------|---------|------------|
| `GET` | `/history` | Get parking history |
| `GET` | `/history/{sl}` | Get history entry details |
| `POST` | `/history/{sl}/retry` | Retry OCR for entry |
| `GET` | `/history/export` | Export CSV |
| `DELETE` | `/history` | Clear history |

---

## Project Structure

```
parking-yolo/
├── main.py                     # FastAPI application entry point
├── detector.py                # YOLOv8 vehicle detection
├── license_plate_detector.py  # YOLOv8 license plate detection
├── video_processor.py        # Video stream processing
├── roi_manager.py           # ROI/slot management
├── plate_ocr.py          # OpenAI + PaddleOCR OCR
├── plate_paddleocr.py     # PaddleOCR plugin
├── history_manager.py     # SQLite history management
├── requirements.txt       # Python dependencies
├── README.md            # This file
├── .env                # Environment variables
│
├── static/               # Static frontend files
│   ├── index.html
│   └── assets/
│
├── frontend/            # React frontend
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       │   ├── VideoPlayer.jsx
│       │   ├── ROIControls.jsx
│       │   ├── StatusPanel.jsx
│       │   ├── RTSPInput.jsx
│       │   └── HistoryPanel.jsx
│       └── utils/
│           └── api.js
│
├── uploads/              # Uploaded video files
├── logs/                # Daily logs
│   └── {date}/
│       ├── snapshots/
│       │   ├── vehicles/
│       │   └── license_plates/
│       └── plate_results.json
│
├── snapshots/           # Vehicle photos
├── rois.json          # Saved ROI configurations
└── parking_history.db  # SQLite database
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI API Key (Optional - for GPT-4o Vision OCR)
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-api-key-here

# Server Configuration (Optional)
HOST=0.0.0.0
PORT=8000
```

### Setting Up OpenAI API Key

1. Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add to `.env` file:
   ```
   OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
   ```
3. If not set, the system will automatically use PaddleOCR fallback

---

## License

MIT License

Copyright (c) 2024 [demo author]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom
the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.

---

<div align="center">

**Parking YOLO** - Smart Parking Management System

Built with YOLOv8 + FastAPI + React

</div>