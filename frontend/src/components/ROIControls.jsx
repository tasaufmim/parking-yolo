import React from "react";
import { Button, InputNumber, Input, Divider } from "antd";
import { BorderOutlined, AimOutlined, DeleteOutlined, SaveOutlined } from "@ant-design/icons";

const MODE = { IDLE: 0, MANUAL: 1, AUTO: 2 };

export default function ROIControls({
  drawMode,
  setDrawMode,
  slotNames,
  setSlotNames,
  currentSlotIndex,
  setCurrentSlotIndex,
  onSaveManual,
  onClear,
  disabled,
}) {
  const slotCount = slotNames.length;

  function handleSlotCountChange(count) {
    const names = Array.from({ length: count }, (_, i) => slotNames[i] || `P${i + 1}`);
    setSlotNames(names);
    setCurrentSlotIndex(0);
  }

  function handleNameChange(index, value) {
    const updated = [...slotNames];
    updated[index] = value;
    setSlotNames(updated);
  }

  return (
    <div className="glass-panel roi-controls">
      <h3 className="panel-title">ROI Drawing</h3>

      <div className="btn-group">
        <Button
          type={drawMode === MODE.MANUAL ? "primary" : "default"}
          icon={<BorderOutlined />}
          onClick={() => { setDrawMode(MODE.MANUAL); setCurrentSlotIndex(0); }}
          disabled={disabled}
          block
        >
          Manual Draw
        </Button>
        <Button
          type={drawMode === MODE.AUTO ? "primary" : "default"}
          icon={<AimOutlined />}
          onClick={() => { setDrawMode(MODE.AUTO); setCurrentSlotIndex(0); }}
          disabled={disabled}
          block
        >
          Auto ROI
        </Button>
      </div>

      {drawMode !== MODE.IDLE && (
        <div className="auto-panel">
          <label className="input-label">
            Number of slots:
            <InputNumber
              min={1}
              max={20}
              value={slotCount}
              onChange={handleSlotCountChange}
              style={{ marginLeft: 8, width: 70 }}
            />
          </label>
          {slotNames.map((name, i) => (
            <div key={i} style={{ marginBottom: 6 }}>
              <Input
                size="small"
                placeholder={`Slot ${i + 1} name`}
                value={name}
                onChange={(e) => handleNameChange(i, e.target.value)}
                style={{ fontFamily: "monospace" }}
              />
            </div>
          ))}
        </div>
      )}

      {drawMode === MODE.MANUAL && slotCount > 0 && (
        <div className="manual-panel">
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={onSaveManual}
            disabled={disabled || currentSlotIndex >= slotCount}
            block
          >
            {currentSlotIndex < slotCount ? `Save "${slotNames[currentSlotIndex] || `Slot ${currentSlotIndex + 1}`}"` : "Done"}
          </Button>
          <p className="hint">
            {currentSlotIndex < slotCount
              ? `Drawing slot ${currentSlotIndex + 1} of ${slotCount} — click 4 points, then save`
              : "All slots drawn"}
          </p>
        </div>
      )}

      {drawMode === MODE.AUTO && (
        <p className="hint">
          Click 4 points around the parking row: top-left, top-right,
          bottom-right, bottom-left
        </p>
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