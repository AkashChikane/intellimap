const API = process.env.REACT_APP_API || "";

async function read(res) {
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export function ingestFile(file) {
  const body = new FormData();
  body.append("file", file);
  return fetch(`${API}/api/ingest`, { method: "POST", body }).then(read);
}

export function ingestSample() {
  return fetch(`${API}/api/ingest/sample`, { method: "POST" }).then(read);
}

export function getRun(runId) {
  return fetch(`${API}/api/runs/${runId}`).then(read);
}

export function getFindings(runId, params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) q.set(k, v);
  });
  const suffix = q.toString() ? `?${q}` : "";
  return fetch(`${API}/api/runs/${runId}/findings${suffix}`).then(read);
}

export function getFrames(runId, type, q = "") {
  const qs = new URLSearchParams({ type, q });
  return fetch(`${API}/api/runs/${runId}/frames?${qs}`).then(read);
}

export function getContext(runId, { frame_type, frame_id, hops = 1, view = "deterministic", hide_unresolved = false }) {
  const qs = new URLSearchParams({
    frame_type,
    frame_id,
    hops: String(hops),
    view,
    hide_unresolved: hide_unresolved ? "true" : "false",
  });
  return fetch(`${API}/api/runs/${runId}/context?${qs}`).then(read);
}

export function generateInsights(runId, body) {
  return fetch(`${API}/api/runs/${runId}/ai/insights`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(read);
}

export function reviewInsight(runId, insightId, status) {
  return fetch(`${API}/api/runs/${runId}/ai/insights/${insightId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  }).then(read);
}

export function chat(runId, body) {
  return fetch(`${API}/api/runs/${runId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(read);
}

export function searchFrame(runId, body) {
  return fetch(`${API}/api/runs/${runId}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(read);
}

export function exportUrl(runId, kind, params) {
  const qs = new URLSearchParams(params);
  return `${API}/api/runs/${runId}/export/${kind}?${qs}`;
}

function filenameFromDisposition(header, fallback) {
  if (!header) return fallback;
  const star = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (star) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      /* keep looking */
    }
  }
  const quoted = header.match(/filename="([^"]+)"/i);
  if (quoted) return quoted[1];
  const bare = header.match(/filename=([^;]+)/i);
  if (bare) return bare[1].trim().replace(/^["']|["']$/g, "");
  return fallback;
}

export async function downloadExport(runId, kind, params, fallbackName) {
  const res = await fetch(exportUrl(runId, kind, params));
  if (!res.ok) {
    let detail = res.statusText;
    const text = await res.text();
    try {
      const data = text ? JSON.parse(text) : null;
      detail = (data && (data.detail || data.message)) || text || detail;
    } catch {
      detail = text || detail;
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const blob = await res.blob();
  const name = filenameFromDisposition(res.headers.get("Content-Disposition"), fallbackName);
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1500);
}

export function getReview(runId) {
  return fetch(`${API}/api/runs/${runId}/review`).then(read);
}

export function getSheetPreview(runId, sheet, limit = 40) {
  const qs = new URLSearchParams({ limit: String(limit) });
  return fetch(
    `${API}/api/runs/${runId}/sheets/${encodeURIComponent(sheet)}/preview?${qs}`
  ).then(read);
}

export function omitSheets(runId, omit) {
  return fetch(`${API}/api/runs/${runId}/review/sheets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ omit }),
  }).then(read);
}

export function scanReview(runId) {
  return fetch(`${API}/api/runs/${runId}/review/ai-scan`, { method: "POST" }).then(read);
}

export function reviewFix(runId, fixId, status) {
  return fetch(`${API}/api/runs/${runId}/review/fixes/${fixId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  }).then(read);
}

export function acceptAllFixes(runId) {
  return fetch(`${API}/api/runs/${runId}/review/fixes/accept-all`, { method: "POST" }).then(read);
}

export async function downloadWorkbook(runId, fallbackName = "intellimap-reviewed.xlsx") {
  const res = await fetch(`${API}/api/runs/${runId}/export/workbook`);
  if (!res.ok) {
    const text = await res.text();
    let detail = res.statusText;
    try {
      const data = text ? JSON.parse(text) : null;
      detail = (data && (data.detail || data.message)) || text || detail;
    } catch {
      detail = text || detail;
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const blob = await res.blob();
  const name = filenameFromDisposition(res.headers.get("Content-Disposition"), fallbackName);
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1500);
}

export function health() {
  return fetch(`${API}/api/health`).then(read);
}
