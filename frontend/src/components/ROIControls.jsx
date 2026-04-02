import React from "react";
import { Button, InputNumber, Divider } from "antd";
import {
  BorderOutlined,
  AimOutlined,
  DeleteOutlined,
  SaveOutlined,
} from "@ant-design/icons";

const MODE = { IDLE: 0, MANUAL: 1, AUTO: 2 };

export default function ROIControls({
  drawMode,
  setDrawMode,
  slotCount,
  setSlotCount,
  onSaveManual,
  onStartAuto,
  onClear,
  disabled,
}) {
  return (
    <div className="glass-panel roi-controls">
      <h3 className="panel-title">ROI Drawing</h3>

      <div className="btn-group">
        <Button
          type={drawMode === MODE.MANUAL ? "primary" : "default"}
          icon={<BorderOutlined />}
          onClick={() => setDrawMode(MODE.MANUAL)}
          disabled={disabled}
          block
        >
          Manual Draw
        </Button>
        <Button
          type={drawMode === MODE.AUTO ? "primary" : "default"}
          icon={<AimOutlined />}
          onClick={() => setDrawMode(MODE.AUTO)}
          disabled={disabled}
          block
        >
          Auto ROI
        </Button>
      </div>

      {drawMode === MODE.AUTO && (
        <div className="auto-panel">
          <label className="input-label">
            Number of slots:
            <InputNumber
              min={1}
              max={20}
              value={slotCount}
              onChange={(v) => setSlotCount(v || 4)}
              style={{ marginLeft: 8, width: 70 }}
            />
          </label>
          <p className="hint">
            Click 4 points around the parking row: top-left, top-right,
            bottom-right, bottom-left
          </p>
        </div>
      )}

      {drawMode === MODE.MANUAL && (
        <div className="manual-panel">
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={onSaveManual}
            block
          >
            Save Slot
          </Button>
          <p className="hint">
            Click polygon points, then save as a parking slot
          </p>
        </div>
      )}

      <Divider style={{ margin: "12px 0", borderColor: "rgba(255,255,255,0.08)" }} />

      <Button
        danger
        icon={<DeleteOutlined />}
        onClick={onClear}
        block
      >
        Clear All ROIs
      </Button>
    </div>
  );
}
