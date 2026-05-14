async function requestJson(path, init) {
  const response = await fetch(path, init);

  if (!response.ok) {
    let detail = `请求失败: ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        detail = payload.detail;
      } else if (payload?.error) {
        detail = payload.error;
      }
    } catch {
      // ignore non-json errors
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export function fetchCollectorAdapterKinds() {
  return requestJson("/api/collect/adapter-kinds");
}

export function fetchCollectorSources() {
  return requestJson("/api/collect/sources");
}

export function fetchCollectorRuns({ limit = 20, sourceId = "" } = {}) {
  const search = new URLSearchParams();
  search.set("limit", String(limit));
  if (sourceId) {
    search.set("source_id", sourceId);
  }
  return requestJson(`/api/collect/runs?${search.toString()}`);
}

export function fetchCollectorRun(runId) {
  return requestJson(`/api/collect/runs/${runId}`);
}

export function createCollectorSource(payload) {
  return requestJson("/api/collect/sources", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateCollectorSource(sourceId, payload) {
  return requestJson(`/api/collect/sources/${sourceId}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteCollectorSource(sourceId) {
  return requestJson(`/api/collect/sources/${sourceId}`, {
    method: "DELETE",
  });
}

export function executeCollector(payload) {
  return requestJson("/api/collect/execute", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}
