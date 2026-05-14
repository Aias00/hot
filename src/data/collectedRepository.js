async function requestJson(path) {
  const response = await fetch(path);

  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`);
  }

  return response.json();
}

export function fetchCollectedItems({
  query = "",
  sourceId = "",
  sourceIds = [],
  tag = "",
  from = "",
  to = "",
  sort = "date",
  dir = "desc",
  page = 1,
  limit = 50,
} = {}) {
  const search = new URLSearchParams();
  if (query.trim()) {
    search.set("q", query.trim());
  }
  if (sourceId) {
    search.set("source_id", sourceId);
  }
  if (sourceIds.length) {
    search.set("source_ids", sourceIds.join(","));
  }
  if (tag) {
    search.set("tag", tag);
  }
  if (from) {
    search.set("from", from);
  }
  if (to) {
    search.set("to", to);
  }
  search.set("sort", sort);
  search.set("dir", dir);
  search.set("page", String(page));
  search.set("limit", String(limit));
  return requestJson(`/api/collected?${search.toString()}`);
}
