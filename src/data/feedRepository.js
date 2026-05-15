export async function loadFeedSnapshot() {
  const response = await fetch("/api/feed");

  if (!response.ok) {
    throw new Error(`无法读取数据: ${response.status}`);
  }

  const payload = await response.json();
  return payload.items;
}

export async function loadFeedPage({
  query = "",
  page = 1,
  limit = 12,
} = {}) {
  const search = new URLSearchParams();
  if (query.trim()) {
    search.set("q", query.trim());
  }
  search.set("page", String(page));
  search.set("limit", String(limit));

  const response = await fetch(`/api/feed?${search.toString()}`);

  if (!response.ok) {
    throw new Error(`无法读取数据: ${response.status}`);
  }

  return response.json();
}
