import React from "react";
import { CarOutlined, ClockCircleOutlined } from "@ant-design/icons";

export default function StatusPanel({ status }) {
  const { slots = [], total = 0, free = 0, occupied = 0, detected = 0 } = status;

  return (
    <div className="glass-panel status-panel">
      <h3 className="panel-title">
        <CarOutlined style={{ marginRight: 8 }} />
        Parking Status
      </h3>

      <div className="status-summary">
        <div className="stat-box">
          <span className="stat-value">{total}</span>
          <span className="stat-label">Total</span>
        </div>
        <div className="stat-box free">
          <span className="stat-value">{free}</span>
          <span className="stat-label">Free</span>
        </div>
        <div className="stat-box occupied">
          <span className="stat-value">{occupied}</span>
          <span className="stat-label">Occupied</span>
        </div>
        <div className="stat-box detected">
          <span className="stat-value">{detected}</span>
          <span className="stat-label">Detected</span>
        </div>
      </div>

      <div className="slot-list">
        {slots.length === 0 ? (
          <p className="empty-text">
            No slots defined. Draw ROIs to start.
          </p>
        ) : (
          slots.map((slot) => (
            <div
              key={slot.id}
              className={`slot-item ${slot.occupied ? "occupied" : "free"} ${slot.pending ? "pending" : ""}`}
            >
              <div className="slot-main-info">
                <span className="slot-id">{slot.id}</span>
                <span className="slot-status">
                  {slot.pending ? (
                    <span className="pending-status">
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      {Math.ceil(slot.remaining_seconds)}s
                    </span>
                  ) : slot.occupied ? (
                    slot.car_id || "OCCUPIED"
                  ) : (
                    "FREE"
                  )}
                </span>
              </div>
              {slot.occupied && slot.plate_text && slot.plate_text !== "N/A" && slot.plate_text !== "processing" && (
                <div className="slot-plate-info">
                  <span className="plate-text">
                    {slot.plate_text} ({slot.plate_color}/{slot.text_color})
                  </span>
                </div>
              )}
              {slot.occupied && slot.plate_status === "processing" && (
                <div className="slot-plate-info processing">
                  <span className="plate-text">Processing OCR...</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
