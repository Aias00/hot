export async function fetchDailySnapshot({ view = "issue", date = "2026-05-08" } = {}) {
  const search = new URLSearchParams();
  search.set("view", view);

  if (view !== "archive") {
    search.set("date", date);
  }

  const response = await fetch(`/api/daily?${search.toString()}`);

  if (!response.ok) {
    throw new Error(`无法读取日报数据: ${response.status}`);
  }

  return response.json();
}
