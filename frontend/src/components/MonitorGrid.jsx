import React, { useState, useEffect, useCallback, useRef } from "react";
import { getConnectedCameras, getAllCameraStatus } from "../utils/api";

const LAYOUTS = {
  "1x2": { cols: 1, rows: 2, label: "1×2" },
  "2x2": { cols: 2, rows: 2, label: "2×2" },
  "2x3": { cols: 2, rows: 3, label: "2×3" },
  "3x3": { cols: 3, rows: 3, label: "3×3" },
  "3x4": { cols: 3, rows: 4, label: "3×4" },
};

const RETRY_INTERVALS = [3000, 6000, 9000, 18000];
const MAX_RETRIES = 10;

function CameraCell({ camera, status, layout }) {
  const [reconnecting, setReconnecting] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [imgKey, setImgKey] = useState(0);
  const retryTimerRef = useRef(null);
  const reconnectLockRef = useRef(false);
  const imgRef = useRef(null);

  const getRetryInterval = () => {
    const idx = Math.min(retryCount, RETRY_INTERVALS.length - 1);
    return RETRY_INTERVALS[idx];
  };

  const handleError = useCallback(() => {
    if (retryCount >= MAX_RETRIES) return;
    if (reconnectLockRef.current) return;
    reconnectLockRef.current = true;
    setReconnecting(true);
    clearTimeout(retryTimerRef.current);
    retryTimerRef.current = setTimeout(() => {
      setRetryCount((c) => c + 1);
      setImgKey((k) => k + 1);
      setReconnecting(false);
      reconnectLockRef.current = false;
    }, getRetryInterval());
  }, [retryCount]);

  const handleLoad = useCallback(() => {
    setReconnecting(false);
    setRetryCount(0);
    clearTimeout(retryTimerRef.current);
    reconnectLockRef.current = false;
  }, []);

  const handleLoadStart = useCallback(() => {
    reconnectLockRef.current = false;
  }, []);

  useEffect(() => {
    setReconnecting(false);
    setRetryCount(0);
    setImgKey((k) => k + 1);
    clearTimeout(retryTimerRef.current);
    reconnectLockRef.current = false;
  }, [camera.id]);

  useEffect(() => {
    return () => clearTimeout(retryTimerRef.current);
  }, []);

  const slotInfo = status
    ? `${status.occupied}/${status.total}`
    : "0/0";

  return (
    <div className="camera-cell">
      <div className="camera-cell-header">
        <span className="camera-cell-name">{camera.name}</span>
        <span className="camera-cell-meta">
          <span className={`status-dot ${reconnecting ? "reconnecting" : "connected"}`} />
          <span className="camera-cell-slots">{slotInfo}</span>
        </span>
      </div>
      <div className="camera-cell-stream">
        <img
          ref={imgRef}
          key={imgKey}
          src={`/cameras/${camera.id}/video_feed`}
          alt={camera.name}
          onError={handleError}
          onLoad={handleLoad}
          onLoadStart={handleLoadStart}
          className={reconnecting ? "img-reconnecting" : ""}
        />
        {reconnecting && (
          <div className="reconnecting-overlay">
            <div className="reconnecting-icon" />
            <span className="reconnecting-text">Reconnecting...</span>
            <span className="reconnecting-hint">
              Attempt {Math.min(retryCount + 1, MAX_RETRIES)} of {MAX_RETRIES}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function PlaceholderCell() {
  return (
    <div className="camera-cell camera-cell-placeholder">
      <div className="placeholder-icon" />
      <span className="placeholder-text">No camera</span>
    </div>
  );
}

export default function MonitorGrid() {
  const [cameras, setCameras] = useState([]);
  const [layout, setLayout] = useState("2x2");
  const [allStatus, setAllStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const pollRef = useRef(null);

  const fetchCameras = useCallback(async () => {
    try {
      const [camList, statusData] = await Promise.all([
        getConnectedCameras(),
        getAllCameraStatus(),
      ]);
      setCameras(camList);

      const statusMap = {};
      if (statusData.cameras) {
        for (const s of statusData.cameras) {
          statusMap[s.cam_id] = s;
        }
      }
      setAllStatus(statusMap);
      setLoading(false);
    } catch (e) {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
    pollRef.current = setInterval(fetchCameras, 5000);
    return () => clearInterval(pollRef.current);
  }, [fetchCameras]);

  const getAutoLayout = (count) => {
    if (count <= 2) return "1x2";
    if (count <= 4) return "2x2";
    if (count <= 6) return "2x3";
    if (count <= 9) return "3x3";
    return "3x4";
  };

  const activeLayout = layout === "auto" ? getAutoLayout(cameras.length) : layout;
  const { cols, rows, label } = LAYOUTS[activeLayout] || LAYOUTS["2x2"];
  const totalCells = cols * rows;

  const totalOccupied = Object.values(allStatus).reduce((s, c) => s + (c.occupied || 0), 0);
  const totalSlots = Object.values(allStatus).reduce((s, c) => s + (c.total || 0), 0);

  return (
    <div className="monitor-grid">
      <div className="monitor-grid-header">
        <div className="monitor-grid-title">
          <span>Monitor Grid</span>
          <span className="monitor-grid-stats">
            {cameras.length} camera{cameras.length !== 1 ? "s" : ""} connected
            {totalSlots > 0 && ` — ${totalOccupied}/${totalSlots} slots occupied`}
          </span>
        </div>
        <div className="grid-layout-selector">
          {Object.keys(LAYOUTS).map((key) => (
            <button
              key={key}
              className={`grid-layout-btn ${layout === key ? "active" : ""}`}
              onClick={() => setLayout(key)}
            >
              {LAYOUTS[key].label}
            </button>
          ))}
          <button
            className={`grid-layout-btn ${layout === "auto" ? "active" : ""}`}
            onClick={() => setLayout("auto")}
          >
            Auto
          </button>
        </div>
      </div>

      <div
        className="camera-grid"
        style={{
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
        }}
      >
        {Array.from({ length: totalCells }).map((_, i) => {
          const cam = cameras[i];
          if (!cam) {
            return <PlaceholderCell key={`placeholder-${i}`} />;
          }
          return (
            <CameraCell
              key={cam.id}
              camera={cam}
              status={allStatus[cam.id]}
              layout={activeLayout}
            />
          );
        })}
      </div>
    </div>
  );
}