import React, { useState, useEffect, useRef, useCallback } from "react";
import { Upload, message } from "antd";
import { InboxOutlined, VideoCameraOutlined, FolderOpenOutlined, HistoryOutlined, SettingOutlined } from "@ant-design/icons";
import VideoPlayer from "./components/VideoPlayer";
import ROIControls from "./components/ROIControls";
import StatusPanel from "./components/StatusPanel";
import RTSPInput from "./components/RTSPInput";
import HistoryPanel from "./components/HistoryPanel";
import CameraManager from "./components/CameraManager";
import { uploadVideo, getResolution, saveROI, clearROIs, getROIs, getCameraStatus } from "./utils/api";

const MODE = { IDLE: 0, MANUAL: 1, AUTO: 2 };

export default function App() {
  const [streamUrl, setStreamUrl] = useState(null);
  const [drawMode, setDrawMode] = useState(MODE.IDLE);
  const [slotCount, setSlotCount] = useState(4);
  const [currentPoints, setCurrentPoints] = useState([]);
  const [videoWidth, setVideoWidth] = useState(0);
  const [videoHeight, setVideoHeight] = useState(0);
  const [status, setStatus] = useState({ slots: [], total: 0, free: 0, occupied: 0, detected: 0, connected: false, source: null });
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");
  const [sourceMode, setSourceMode] = useState("rtsp");
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [activeCameraId, setActiveCameraId] = useState(null);
  const [page, setPage] = useState("main");
  const statusInterval = useRef(null);

  const fetchStatus = useCallback(async () => {
    if (!activeCameraId) return;
    try {
      const data = await getCameraStatus(activeCameraId);
      setStatus(data);
      setConnected(data.connected || false);
    } catch (e) {}
  }, [activeCameraId]);

  useEffect(() => {
    if (!streamUrl) return;
    fetchStatus();
    statusInterval.current = setInterval(fetchStatus, 2000);
    return () => clearInterval(statusInterval.current);
  }, [streamUrl, fetchStatus]);

  async function handleUpload(file) {
    setUploading(true);
    setFileName(file.name);
    try {
      const data = await uploadVideo(file);
      if (data.message) {
        message.success("Video uploaded successfully");
        setConnected(true);
        setStreamUrl("/video_feed?" + Date.now());
        const res = await getResolution();
        setVideoWidth(res.width);
        setVideoHeight(res.height);
      }
    } catch (e) {
      message.error("Upload failed: " + e.message);
    }
    setUploading(false);
    return false;
  }

  async function handleRTSPConnect(camera) {
    setConnecting(true);
    try {
      setConnected(true);
      setStreamUrl(`/cameras/${camera.id}/video_feed?` + Date.now());
      try {
        const res = await fetch(`/cameras/${camera.id}/resolution`);
        const data = await res.json();
        setVideoWidth(data.width);
        setVideoHeight(data.height);
      } catch (e) {}
    } catch (e) {}
    setConnecting(false);
  }

  async function handleRTSPDisconnect(camId) {
    setConnected(false);
    setStreamUrl(null);
    setActiveCameraId(null);
  }

  function handleCameraChange(camId) {
    setActiveCameraId(camId);
  }

  function scaleToVideo(points) {
    const img = document.querySelector(".video-feed");
    if (!img || !videoWidth || !videoHeight) return points;
    const rect = img.getBoundingClientRect();
    return points.map(([x, y]) => [
      Math.round((x * videoWidth) / rect.width),
      Math.round((y * videoHeight) / rect.height),
    ]);
  }

  async function handleSaveManual() {
    if (!activeCameraId) {
      message.warning("Connect a camera first");
      return;
    }
    if (currentPoints.length < 3) {
      message.warning("Need at least 3 points");
      return;
    }
    try {
      const scaled = scaleToVideo(currentPoints);
      const data = await saveROI(activeCameraId, scaled);
      message.success(`Slot ${data.slot.id} saved`);
      setCurrentPoints([]);
      setDrawMode(MODE.IDLE);
    } catch (e) {
      message.error("Save failed");
    }
  }

  async function handleSlotGenerated(slots, rawPoints) {
    if (!activeCameraId) {
      message.warning("Connect a camera first");
      return;
    }
    try {
      if (!videoWidth || !videoHeight) {
        const res = await fetch(`/cameras/${activeCameraId}/resolution`);
        if (res.ok) {
          const data = await res.json();
          setVideoWidth(data.width);
          setVideoHeight(data.height);
        }
      }
      const scaledSlots = slots.map((slot) => scaleToVideo(slot));
      for (let i = 0; i < scaledSlots.length; i++) {
        await saveROI(activeCameraId, scaledSlots[i], `P${i + 1}`);
      }
      message.success(`${slots.length} slots saved`);
      setCurrentPoints([]);
      setDrawMode(MODE.IDLE);
    } catch (e) {
      message.error("Save failed");
    }
  }

  async function handleClear() {
    if (!activeCameraId) return;
    await clearROIs(activeCameraId);
    setCurrentPoints([]);
    setDrawMode(MODE.IDLE);
    message.success("All ROIs cleared");
  }

  const tabs = null;

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>Parking Management System</h1>
          {connected && <span className="connected-badge">● Live</span>}
        </div>
        <div className="header-nav">
          <button
            className={`nav-btn ${page === "main" ? "active" : ""}`}
            onClick={() => setPage("main")}
          >
            <VideoCameraOutlined />
            <span>Monitor</span>
          </button>
          <button
            className={`nav-btn ${page === "cameras" ? "active" : ""}`}
            onClick={() => setPage("cameras")}
          >
            <SettingOutlined />
            <span>Cameras</span>
          </button>
          <button
            className={`nav-btn ${page === "history" ? "active" : ""}`}
            onClick={() => setPage("history")}
          >
            <HistoryOutlined />
            <span>History</span>
          </button>
        </div>
      </header>

      {page === "cameras" ? (
        <CameraManager />
      ) : page === "history" ? (
        <HistoryPanel />
      ) : (
        <div className="main-area">
          <div className="source-panel">
            <div className="source-tabs">
              <button
                className={`tab-btn ${sourceMode === "upload" ? "active" : ""}`}
                onClick={() => setSourceMode("upload")}
              >
                <FolderOpenOutlined />
                <span>Upload Video</span>
              </button>
              <button
                className={`tab-btn ${sourceMode === "rtsp" ? "active" : ""}`}
                onClick={() => setSourceMode("rtsp")}
              >
                <VideoCameraOutlined />
                <span>RTSP Live</span>
              </button>
            </div>
            {sourceMode === "upload" ? (
              <Upload.Dragger
                accept=".mp4,.avi,.mov,.mkv"
                showUploadList={false}
                beforeUpload={handleUpload}
                disabled={uploading}
                className="source-upload-dragger"
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">
                  {uploading ? "Uploading..." : "Click or drag video file here"}
                </p>
                <p className="ant-upload-hint">Supports MP4, AVI, MOV, MKV</p>
              </Upload.Dragger>
            ) : (
              <RTSPInput
                onConnect={handleRTSPConnect}
                onDisconnect={handleRTSPDisconnect}
                onCameraChange={handleCameraChange}
                activeCameraId={activeCameraId}
                connecting={connecting}
                connected={connected}
              />
            )}
          </div>

          <div className="content-area">
            <div className="video-section">
              <VideoPlayer
                streamUrl={streamUrl}
                videoWidth={videoWidth}
                videoHeight={videoHeight}
                drawMode={drawMode}
                currentPoints={currentPoints}
                onPointsChange={setCurrentPoints}
                onSlotGenerated={handleSlotGenerated}
                slotCount={slotCount}
              />
            </div>

            <div className="controls-section">
              <ROIControls
                drawMode={drawMode}
                setDrawMode={(m) => {
                  setDrawMode(m);
                  setCurrentPoints([]);
                }}
                slotCount={slotCount}
                setSlotCount={setSlotCount}
                onSaveManual={handleSaveManual}
                onClear={handleClear}
                disabled={!streamUrl}
              />
              <StatusPanel status={status} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
