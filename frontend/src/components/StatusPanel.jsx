import React from "react";
import { CarOutlined } from "@ant-design/icons";

export default function StatusPanel({ status }) {
  const { slots = [], total = 0, free = 0, occupied = 0 } = status;

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
              className={`slot-item ${slot.occupied ? "occupied" : "free"}`}
            >
              <span className="slot-id">{slot.id}</span>
              <span className="slot-status">
                {slot.occupied ? "OCCUPIED" : "FREE"}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
