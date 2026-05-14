export async function loadFeedSnapshot() {
  const response = await fetch("/api/feed");

  if (!response.ok) {
    throw new Error(`无法读取数据: ${response.status}`);
  }

  const payload = await response.json();
  return payload.items;
}
