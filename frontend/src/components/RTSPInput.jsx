import React, { useState } from "react";
import { Input, Button, Space } from "antd";
import { LinkOutlined, DisconnectOutlined, LoadingOutlined } from "@ant-design/icons";

export default function RTSPInput({ onConnect, onDisconnect, connecting, connected }) {
  const [url, setUrl] = useState("");

  function handleConnect() {
    if (!url.trim()) return;
    onConnect(url.trim());
  }

  function handleDisconnect() {
    onDisconnect();
  }

  return (
    <div className="rtsp-input-container">
      <div className="rtsp-form">
        <label className="rtsp-label">
          <LinkOutlined style={{ marginRight: 8 }} />
          RTSP URL
        </label>
        <Input
          placeholder="rtsp://192.168.1.100:554/stream"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onPressEnter={handleConnect}
          disabled={connected || connecting}
          className="rtsp-url-input"
        />
      </div>

      <Space style={{ marginTop: 12, width: "100%" }} block>
        <Button
          type="primary"
          onClick={handleConnect}
          disabled={connected || connecting || !url.trim()}
          icon={connecting ? <LoadingOutlined /> : <LinkOutlined />}
          style={{ flex: 1 }}
        >
          {connecting ? "Connecting..." : "Connect"}
        </Button>
        <Button
          danger
          onClick={handleDisconnect}
          disabled={!connected && !connecting}
          icon={<DisconnectOutlined />}
          style={{ flex: 1 }}
        >
          Disconnect
        </Button>
      </Space>

      <div className="rtsp-status">
        <span className={`status-dot ${connected ? "connected" : "disconnected"}`} />
        <span className="status-text">
          {connected ? "Connected" : connecting ? "Connecting..." : "Disconnected"}
        </span>
      </div>
    </div>
  );
}
