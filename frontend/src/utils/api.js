export async function uploadVideo(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/upload", { method: "POST", body: formData });
  return res.json();
}

export async function connectRTSP(url) {
  const res = await fetch("/connect_rtsp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Connection failed");
  }
  return res.json();
}

export async function disconnectStream() {
  const res = await fetch("/disconnect", { method: "POST" });
  return res.json();
}

export async function getResolution() {
  const res = await fetch("/resolution");
  return res.json();
}

export async function getSnapshot() {
  const res = await fetch("/snapshot");
  return res.blob();
}

export async function getStatus() {
  const res = await fetch("/status");
  return res.json();
}

export async function getHistory(page = 1, perPage = 100, status = null) {
  const params = new URLSearchParams({ page, per_page: perPage });
  if (status) params.append("status", status);
  const res = await fetch(`/history?${params}`);
  return res.json();
}

export async function getHistoryDetail(sl) {
  const res = await fetch(`/history/${sl}`);
  return res.json();
}

export async function retryOCR(sl) {
  const res = await fetch(`/history/${sl}/retry`, { method: "POST" });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Retry failed");
  }
  return res.json();
}

export async function exportHistory() {
  const res = await fetch("/history/export");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "parking_history.csv";
  a.click();
  window.URL.revokeObjectURL(url);
}

export async function clearHistory() {
  const res = await fetch("/history", { method: "DELETE" });
  return res.json();
}

export async function getCameras() {
  const res = await fetch("/cameras");
  return res.json();
}

export async function addCamera(name, rtsp_url) {
  const res = await fetch("/cameras", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, rtsp_url }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to add camera");
  }
  return res.json();
}

export async function updateCamera(id, name, rtsp_url) {
  const res = await fetch(`/cameras/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, rtsp_url }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to update camera");
  }
  return res.json();
}

export async function deleteCamera(id) {
  const res = await fetch(`/cameras/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to delete camera");
  }
  return res.json();
}

export async function toggleCameraEnabled(id, enabled) {
  const res = await fetch(`/cameras/${id}/enable`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to toggle camera");
  }
  return res.json();
}

export async function connectCamera(id) {
  const res = await fetch(`/cameras/${id}/connect`, { method: "POST" });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to connect camera");
  }
  return res.json();
}

export async function disconnectCamera(id) {
  const res = await fetch(`/cameras/${id}/disconnect`, { method: "POST" });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to disconnect camera");
  }
  return res.json();
}

export async function getCameraStatus(id) {
  const res = await fetch(`/cameras/${id}/status`);
  return res.json();
}

export async function getAllCameraStatus() {
  const res = await fetch(`/cameras/all_status`);
  return res.json();
}

export async function saveCameraROI(camId, points, slotId) {
  const body = { points };
  if (slotId) body.slot_id = slotId;
  const res = await fetch(`/cameras/${camId}/roi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function clearCameraROIs(camId) {
  const res = await fetch(`/cameras/${camId}/roi`, { method: "DELETE" });
  return res.json();
}

export async function getCameraROIs(camId) {
  const res = await fetch(`/cameras/${camId}/roi`);
  return res.json();
}

export async function saveROI(camId, points, slotId) {
  const body = { points };
  if (slotId) body.slot_id = slotId;
  const res = await fetch(`/cameras/${camId}/roi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function clearROIs(camId) {
  const res = await fetch(`/cameras/${camId}/roi`, { method: "DELETE" });
  return res.json();
}

export async function getROIs(camId) {
  const res = await fetch(`/cameras/${camId}/roi`);
  return res.json();
}
