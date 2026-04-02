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
