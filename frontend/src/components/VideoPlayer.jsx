import React, { useRef, useEffect, useState, useCallback } from "react";

const MODE = { IDLE: 0, MANUAL: 1, AUTO: 2 };

export default function VideoPlayer({
  streamUrl,
  videoWidth,
  videoHeight,
  drawMode,
  onPointsChange,
  currentPoints,
  onSlotGenerated,
  slotCount,
}) {
  const imgRef = useRef(null);
  const canvasRef = useRef(null);
  const [imgLoaded, setImgLoaded] = useState(false);

  useEffect(() => {
    if (!imgLoaded || !imgRef.current) return;
    const rect = imgRef.current.getBoundingClientRect();
    const canvas = canvasRef.current;
    canvas.width = rect.width;
    canvas.height = rect.height;
    redraw();
  }, [imgLoaded, currentPoints, drawMode]);

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (drawMode === MODE.AUTO && currentPoints.length >= 2) {
      drawAutoPoints(ctx, canvas);
    } else if (drawMode === MODE.MANUAL && currentPoints.length >= 1) {
      drawManualPoints(ctx);
    }
  }, [currentPoints, drawMode]);

  function drawManualPoints(ctx) {
    ctx.strokeStyle = "#00ff00";
    ctx.fillStyle = "#00ff00";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(currentPoints[0][0], currentPoints[0][1]);
    for (let i = 1; i < currentPoints.length; i++) {
      ctx.lineTo(currentPoints[i][0], currentPoints[i][1]);
    }
    ctx.stroke();
    for (const [x, y] of currentPoints) {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawAutoPoints(ctx) {
    ctx.strokeStyle = "#00ff00";
    ctx.fillStyle = "#00ff00";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(currentPoints[0][0], currentPoints[0][1]);
    for (let i = 1; i < currentPoints.length; i++) {
      ctx.lineTo(currentPoints[i][0], currentPoints[i][1]);
    }
    if (currentPoints.length === 4) ctx.closePath();
    ctx.stroke();

    const labels = ["1", "2", "3", "4"];
    for (let i = 0; i < currentPoints.length; i++) {
      const [x, y] = currentPoints[i];
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px sans-serif";
      ctx.fillText(labels[i], x + 8, y - 8);
      ctx.fillStyle = "#00ff00";
    }
  }

  function drawGeneratedSlots(ctx, slots) {
    const colors = ["#00ff00", "#00cc00", "#009900", "#006600"];
    for (let i = 0; i < slots.length; i++) {
      const slot = slots[i];
      ctx.strokeStyle = colors[i % colors.length];
      ctx.fillStyle = colors[i % colors.length] + "33";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(slot[0][0], slot[0][1]);
      for (let j = 1; j < slot.length; j++) {
        ctx.lineTo(slot[j][0], slot[j][1]);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      const cx = (slot[0][0] + slot[2][0]) / 2;
      const cy = (slot[0][1] + slot[2][1]) / 2;
      ctx.fillStyle = "#fff";
      ctx.font = "bold 14px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`P${i + 1}`, cx, cy + 5);
    }
  }

  function lerp(a, b, t) {
    return [
      Math.round(a[0] + (b[0] - a[0]) * t),
      Math.round(a[1] + (b[1] - a[1]) * t),
    ];
  }

  function generateSlots(quad, n) {
    const [p1, p2, p3, p4] = quad;
    const slots = [];
    for (let i = 0; i < n; i++) {
      const t1 = i / n;
      const t2 = (i + 1) / n;
      slots.push([
        lerp(p1, p2, t1),
        lerp(p1, p2, t2),
        lerp(p4, p3, t2),
        lerp(p4, p3, t1),
      ]);
    }
    return slots;
  }

  const handleCanvasClick = useCallback(
    (e) => {
      if (drawMode === MODE.IDLE) return;
      const rect = imgRef.current.getBoundingClientRect();
      const x = Math.round(e.clientX - rect.left);
      const y = Math.round(e.clientY - rect.top);
      const newPoints = [...currentPoints, [x, y]];

      if (drawMode === MODE.AUTO && newPoints.length === 4) {
        const slots = generateSlots(newPoints, slotCount || 4);
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawGeneratedSlots(ctx, slots);
        onSlotGenerated(slots, newPoints);
      } else {
        onPointsChange(newPoints);
      }
    },
    [drawMode, currentPoints, slotCount, onPointsChange, onSlotGenerated]
  );

  function scaleToVideo(points) {
    if (!imgRef.current || !videoWidth || !videoHeight) return points;
    const rect = imgRef.current.getBoundingClientRect();
    return points.map(([x, y]) => [
      Math.round((x * videoWidth) / rect.width),
      Math.round((y * videoHeight) / rect.height),
    ]);
  }

  return (
    <div className="video-player">
      {streamUrl ? (
        <img
          ref={imgRef}
          src={streamUrl}
          alt="Video stream"
          className="video-feed"
          onLoad={() => setImgLoaded(true)}
        />
      ) : (
        <div className="video-placeholder">
          Upload a video to start monitoring
        </div>
      )}
      <canvas
        ref={canvasRef}
        className="video-canvas"
        onClick={handleCanvasClick}
        style={{
          cursor: drawMode !== MODE.IDLE ? "crosshair" : "default",
          display: streamUrl ? "block" : "none",
        }}
      />
    </div>
  );
}
