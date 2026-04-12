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

export async function saveROI(points, slotId) {
  const body = { points };
  if (slotId) body.slot_id = slotId;
  const res = await fetch("/roi", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function clearROIs() {
  const res = await fetch("/roi", { method: "DELETE" });
  return res.json();
}

export async function getROIs() {
  const res = await fetch("/roi");
  return res.json();
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
