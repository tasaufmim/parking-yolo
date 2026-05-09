import React, { useState, useEffect } from "react";
import { Select, Space, Tag, Tooltip } from "antd";
import { LoadingOutlined, DisconnectOutlined } from "@ant-design/icons";
import { getCameras, connectCamera, disconnectCamera } from "../utils/api";

export default function RTSPInput({ onConnect, onDisconnect, onCameraChange, activeCameraId, connecting, connected }) {
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [loadingCameras, setLoadingCameras] = useState(false);
  const [connectingId, setConnectingId] = useState(null);

  const fetchCameras = async () => {
    setLoadingCameras(true);
    try {
      const data = await getCameras();
      setCameras(data.cameras || []);
    } catch (e) {
      console.error("Failed to load cameras", e);
    }
    setLoadingCameras(false);
  };

  useEffect(() => {
    fetchCameras();
  }, []);

  useEffect(() => {
    if (activeCameraId) {
      setSelectedCamera(activeCameraId);
    }
  }, [activeCameraId]);

  const handleChange = async (camId) => {
    if (!camId) return;

    const cam = cameras.find((c) => c.id === camId);
    if (!cam) return;

    if (selectedCamera && selectedCamera !== camId) {
      try {
        await disconnectCamera(selectedCamera);
        onDisconnect?.(selectedCamera);
      } catch (e) {
        console.error("Disconnect failed", e);
      }
    }

    setConnectingId(camId);
    try {
      await connectCamera(camId);
      setSelectedCamera(camId);
      onCameraChange?.(camId);
      onConnect?.(cam);
    } catch (e) {
      console.error("Connect failed", e);
    }
    setConnectingId(null);
  };

  const handleDisconnect = async () => {
    if (!selectedCamera) return;
    try {
      await disconnectCamera(selectedCamera);
      onDisconnect?.(selectedCamera);
      setSelectedCamera(null);
      onCameraChange?.(null);
    } catch (e) {
      console.error("Disconnect failed", e);
    }
  };

  const options = cameras.map((cam) => ({
    value: cam.id,
    label: cam.enabled ? cam.name : `${cam.name} (disabled)`,
    disabled: !cam.enabled,
  }));

  if (cameras.length === 0 && !loadingCameras) {
    return (
      <div className="rtsp-status">
        <span className="status-dot disconnected" />
        <span className="status-text">
          No cameras configured. Go to Cameras page to add one.
        </span>
      </div>
    );
  }

  const selectedCam = cameras.find((c) => c.id === selectedCamera);
  const isLoading = connectingId !== null;

  return (
    <div className="rtsp-input-container">
      <div className="rtsp-select-row">
        <Select
          placeholder="Select a camera"
          value={selectedCamera}
          options={options}
          onChange={handleChange}
          loading={isLoading}
          disabled={isLoading}
          style={{ flex: 1 }}
          suffixIcon={isLoading ? <LoadingOutlined /> : null}
        />
        {selectedCamera && (
          <Tooltip title="Disconnect">
            <button className="rtsp-disconnect-btn" onClick={handleDisconnect}>
              <DisconnectOutlined />
            </button>
          </Tooltip>
        )}
      </div>
      {selectedCamera && selectedCam && (
        <div className="rtsp-status">
          <span className="status-dot connected" />
          <span className="status-text">
            <strong>{selectedCam.name}</strong>
          </span>
          <Space style={{ marginLeft: "auto" }}>
            <Tag color="green">Live</Tag>
          </Space>
        </div>
      )}
    </div>
  );
}