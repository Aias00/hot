export async function fetchMpSnapshot({ query = "", since = "30d", page = "1" } = {}) {
  const search = new URLSearchParams();

  if (query.trim()) {
    search.set("q", query.trim());
  }

  search.set("since", since);
  search.set("page", String(page || "1"));

  const response = await fetch(`/api/mp?${search.toString()}`);

  if (!response.ok) {
    throw new Error(`无法读取公众号爆文数据: ${response.status}`);
  }

  return response.json();
}
