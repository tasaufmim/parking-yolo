import React, { useState, useEffect, useCallback, useRef } from "react";
import { Table, Button, Modal, Tag, message, Select, Space, Tooltip } from "antd";
import { ReloadOutlined, DownloadOutlined, DeleteOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined } from "@ant-design/icons";
import { getHistory, getHistoryDetail, retryOCR, exportHistory, clearHistory } from "../utils/api";

const PER_PAGE_OPTIONS = [100, 125, 150, 200, 250];

function calculateLiveDuration(timeParked, timeLeft = null) {
  if (!timeParked) return null;
  const start = new Date(timeParked);
  const end = timeLeft ? new Date(timeLeft) : new Date();
  const diffMs = end - start;
  if (diffMs < 0) return null;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours < 24) return mins === 0 ? `${hours}h` : `${hours}h ${mins}m`;
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return `${days}d ${remainingHours}h`;
}

function formatDuration(minutes) {
  if (!minutes) return "-";
  if (minutes < 60) return `${minutes}m`;
  const hrs = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (mins === 0) return `${hrs}h`;
  return `${hrs}h ${mins}m`;
}

function formatTime(isoString) {
  if (!isoString) return "-";
  try {
    const dt = new Date(isoString);
    return dt.toLocaleString("en-IN", { 
      day: "numeric", 
      month: "short", 
      hour: "2-digit", 
      minute: "2-digit",
      second: "2-digit"
    });
  } catch {
    return "-";
  }
}

export default function HistoryPanel() {
  const [data, setData] = useState({ entries: [], total: 0, page: 1, per_page: 100, total_pages: 0 });
  const [loading, setLoading] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [retrying, setRetrying] = useState(null);
  const perPage = PER_PAGE_OPTIONS[0];
  const refreshInterval = useRef(null);
  const [, forceUpdate] = useState(0);

  const fetchData = useCallback(async (page = 1) => {
    setLoading(true);
    try {
      const result = await getHistory(page, perPage);
      setData(result);
    } catch (e) {
      message.error("Failed to load history");
    }
    setLoading(false);
  }, [perPage]);

  useEffect(() => {
    fetchData(1);
    // Refresh every 10 seconds for live duration
    refreshInterval.current = setInterval(() => {
      forceUpdate(n => n + 1);
    }, 10000);
    return () => {
      if (refreshInterval.current) clearInterval(refreshInterval.current);
    };
  }, [fetchData]);

  const handleRetry = async (sl) => {
    setRetrying(sl);
    try {
      await retryOCR(sl);
      message.success("OCR retried successfully");
      const updated = await getHistoryDetail(sl);
      setSelectedEntry(updated);
      fetchData(data.page);
    } catch (e) {
      message.error("Retry failed: " + e.message);
    }
    setRetrying(null);
  };

  const handleExport = async () => {
    try {
      await exportHistory();
      message.success("History exported");
    } catch (e) {
      message.error("Export failed");
    }
  };

  const handleClear = async () => {
    Modal.confirm({
      title: "Clear History",
      content: "Are you sure you want to clear all history?",
      onOk: async () => {
        try {
          await clearHistory();
          message.success("History cleared");
          fetchData(1);
        } catch (e) {
          message.error("Failed to clear history");
        }
      },
    });
  };

  const columns = [
    {
      title: "SL",
      dataIndex: "sl",
      key: "sl",
      width: 60,
    },
    {
      title: "Slot",
      dataIndex: "slot_id",
      key: "slot_id",
      width: 80,
    },
    {
      title: "Car ID",
      dataIndex: "car_id",
      key: "car_id",
      width: 130,
    },
    {
      title: "Plate #",
      dataIndex: "plate_number",
      key: "plate_number",
      width: 120,
      render: (val) => val || "-",
    },
    {
      title: "Vehicle Type",
      dataIndex: "vehicle_type",
      key: "vehicle_type",
      width: 140,
      render: (val) => {
        const colors = {
          "Private": "blue",
          "Commercial": "orange",
          "Private Electric": "green",
          "Commercial Electric": "cyan",
          "Self-drive Rental": "magenta",
          "Temporary/Dealer": "red",
          "Diplomatic": "purple",
          "Unknown": "default",
        };
        return <Tag color={colors[val] || "default"}>{val || "Unknown"}</Tag>;
      },
    },
    {
      title: "Time In",
      dataIndex: "time_parked",
      key: "time_parked",
      width: 150,
      render: (val) => formatTime(val),
    },
    {
      title: "Time Out",
      dataIndex: "time_left",
      key: "time_left",
      width: 150,
      render: (val) => formatTime(val),
    },
    {
      title: "Duration",
      dataIndex: "duration_minutes",
      key: "duration_minutes",
      width: 100,
      render: (_, record) => {
        const liveDur = calculateLiveDuration(record.time_parked, record.time_left);
        return (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {record.status === 'active' && <span className="blinking-dot" />}
            {liveDur || "-"}
          </span>
        );
      },
    },
    {
      title: "Action",
      key: "action",
      width: 100,
      render: (_, record) => {
        const canRetry = 
          record.retry_status !== "pending" &&
          record.car_photo_path &&
          (!record.plate_color || !record.plate_number || !record.text_color);

        if (retrying === record.sl) {
          return <LoadingOutlined spin />;
        }

        if (record.retry_status === "success") {
          return <CheckCircleOutlined style={{ color: "green" }} />;
        }

        if (record.retry_status === "failed") {
          return <CloseCircleOutlined style={{ color: "red" }} />;
        }

        return (
          <Tooltip title={!record.car_photo_path ? "No car photo available" : "Retry OCR"}>
            <Button
              type="link"
              icon={<ReloadOutlined />}
              onClick={() => handleRetry(record.sl)}
              disabled={!canRetry}
              size="small"
            />
          </Tooltip>
        );
      },
    },
  ];

  const pagination = {
    current: data.page,
    pageSize: data.per_page,
    total: data.total,
    onChange: fetchData,
    showSizeChanger: false,
  };

  return (
    <div className="history-panel">
      <div className="history-header">
        <Space>
          <Select
            defaultValue={100}
            style={{ width: 100 }}
            options={PER_PAGE_OPTIONS.map((n) => ({ label: `${n}`, value: n }))}
            onChange={(val) => {
              fetchData(1);
            }}
          />
          <span>entries per page</span>
        </Space>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>
            Export CSV
          </Button>
          <Button icon={<DeleteOutlined />} danger onClick={handleClear}>
            Clear All
          </Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={data.entries}
        rowKey="sl"
        loading={loading}
        pagination={pagination}
        size="small"
        scroll={{ x: 1100 }}
        onRow={(record) => ({
          onClick: async () => {
            const detail = await getHistoryDetail(record.sl);
            setSelectedEntry(detail);
            setModalVisible(true);
          },
          style: { cursor: "pointer" },
        })}
      />

      <Modal
        title={`Parking Details - SL: ${selectedEntry?.sl}`}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        {selectedEntry && (
          <div className="detail-grid">
            <div className="detail-row">
              <span className="detail-label">SL:</span>
              <span className="detail-value">{selectedEntry.sl}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Slot ID:</span>
              <span className="detail-value">{selectedEntry.slot_id}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Car ID:</span>
              <span className="detail-value">{selectedEntry.car_id}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">License Plate:</span>
              <span className="detail-value">{selectedEntry.plate_number || "N/A"}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Plate Color:</span>
              <span className="detail-value">{selectedEntry.plate_color || "N/A"}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Text Color:</span>
              <span className="detail-value">{selectedEntry.text_color || "N/A"}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Vehicle Type:</span>
              <span className="detail-value">{selectedEntry.vehicle_type || "Unknown"}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">OCR Source:</span>
              <span className="detail-value">
                {selectedEntry.ocr_source === "openai" ? "Primary" : 
                 selectedEntry.ocr_source === "paddleocr" ? "Secondary" : 
                 "N/A"}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Time Parked:</span>
              <span className="detail-value">{formatTime(selectedEntry.time_parked)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Time Left:</span>
              <span className="detail-value">{formatTime(selectedEntry.time_left)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Duration:</span>
              <span className="detail-value">{formatDuration(selectedEntry.duration_minutes)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Status:</span>
              <span className="detail-value">{selectedEntry.status}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Retry Status:</span>
              <span className="detail-value">{selectedEntry.retry_status || "none"}</span>
            </div>
            {selectedEntry.car_photo_path && (
              <div className="detail-row">
                <span className="detail-label">Car Photo:</span>
                <span className="detail-value">
                  <img 
                    src={`/${selectedEntry.car_photo_path}`} 
                    alt="Car" 
                    style={{ maxWidth: 200, maxHeight: 150, marginTop: 8 }}
                  />
                </span>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}