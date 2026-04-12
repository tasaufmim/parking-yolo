import React, { useState, useEffect, useRef, useCallback } from "react";
import { Upload, message } from "antd";
import { InboxOutlined, VideoCameraOutlined, FolderOpenOutlined, HistoryOutlined } from "@ant-design/icons";
import VideoPlayer from "./components/VideoPlayer";
import ROIControls from "./components/ROIControls";
import StatusPanel from "./components/StatusPanel";
import RTSPInput from "./components/RTSPInput";
import HistoryPanel from "./components/HistoryPanel";
import { uploadVideo, getResolution, saveROI, clearROIs, getStatus, connectRTSP, disconnectStream } from "./utils/api";

const MODE = { IDLE: 0, MANUAL: 1, AUTO: 2 };

export default function App() {
  const [streamUrl, setStreamUrl] = useState(null);
  const [drawMode, setDrawMode] = useState(MODE.IDLE);
  const [slotCount, setSlotCount] = useState(4);
  const [currentPoints, setCurrentPoints] = useState([]);
  const [videoWidth, setVideoWidth] = useState(0);
  const [videoHeight, setVideoHeight] = useState(0);
  const [status, setStatus] = useState({ slots: [], total: 0, free: 0, occupied: 0, connected: false, source: null });
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");
  const [sourceMode, setSourceMode] = useState("upload"); // "upload" | "rtsp" | "history"
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const statusInterval = useRef(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getStatus();
      setStatus(data);
      setConnected(data.connected || false);
    } catch (e) {}
  }, []);

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

  async function handleRTSPConnect(url) {
    setConnecting(true);
    try {
      await connectRTSP(url);
      message.success("Connected to RTSP stream");
      setConnected(true);
      setStreamUrl("/video_feed?" + Date.now());
      try {
        const res = await getResolution();
        setVideoWidth(res.width);
        setVideoHeight(res.height);
      } catch (e) {
        // Resolution may not be available immediately
      }
    } catch (e) {
      message.error("Connection failed: " + e.message);
    }
    setConnecting(false);
  }

  async function handleRTSPDisconnect() {
    await disconnectStream();
    setConnected(false);
    setStreamUrl(null);
    message.success("Disconnected");
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
    if (currentPoints.length < 3) {
      message.warning("Need at least 3 points");
      return;
    }
    try {
      const scaled = scaleToVideo(currentPoints);
      const data = await saveROI(scaled);
      message.success(`Slot ${data.slot.id} saved`);
      setCurrentPoints([]);
      setDrawMode(MODE.IDLE);
    } catch (e) {
      message.error("Save failed");
    }
  }

  async function handleSlotGenerated(slots, rawPoints) {
    try {
      if (!videoWidth || !videoHeight) {
        const res = await getResolution();
        setVideoWidth(res.width);
        setVideoHeight(res.height);
      }
      const scaledSlots = slots.map((slot) => scaleToVideo(slot));
      for (let i = 0; i < scaledSlots.length; i++) {
        await saveROI(scaledSlots[i], `P${i + 1}`);
      }
      message.success(`${slots.length} slots saved`);
      setCurrentPoints([]);
      setDrawMode(MODE.IDLE);
    } catch (e) {
      message.error("Save failed");
    }
  }

  async function handleClear() {
    await clearROIs();
    setCurrentPoints([]);
    setDrawMode(MODE.IDLE);
    message.success("All ROIs cleared");
  }

  const tabs = [
    { key: "upload", label: "Upload Video", icon: <FolderOpenOutlined /> },
    { key: "rtsp", label: "RTSP Live Stream", icon: <VideoCameraOutlined /> },
    { key: "history", label: "History", icon: <HistoryOutlined /> },
  ];

  return (
    <div className="app">
      <header className="app-header">
        <h1>Parking Management System</h1>
        {connected && <span className="connected-badge">● Live</span>}
      </header>

      <div className="source-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab-btn ${sourceMode === tab.key ? "active" : ""}`}
            onClick={() => setSourceMode(tab.key)}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="source-panel glass-panel">
        {sourceMode === "upload" ? (
          <div className="upload-area">
            <Upload.Dragger
              accept=".mp4,.avi,.mov,.mkv"
              showUploadList={false}
              beforeUpload={handleUpload}
              disabled={uploading}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                {uploading ? "Uploading..." : "Click or drag video file here"}
              </p>
              <p className="ant-upload-hint">Supports MP4, AVI, MOV, MKV</p>
            </Upload.Dragger>
          </div>
        ) : sourceMode === "rtsp" ? (
          <RTSPInput
            onConnect={handleRTSPConnect}
            onDisconnect={handleRTSPDisconnect}
            connecting={connecting}
            connected={connected}
          />
        ) : (
          <HistoryPanel />
        )}
      </div>

      {sourceMode !== "history" && (
        <div className="main-area">
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
      )}
    </div>
  );
}
