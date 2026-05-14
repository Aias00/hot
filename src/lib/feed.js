function hashString(input) {
  return [...input].reduce((acc, char) => acc + char.charCodeAt(0), 0);
}

export function getAvatarLabel(source) {
  return source
    .replace(/（.*?）/g, "")
    .replace(/[：:]/g, " ")
    .trim()
    .slice(0, 2)
    .toUpperCase();
}

export function getSearchText(item) {
  return [
    item.day,
    item.time,
    item.source,
    item.handle,
    item.title,
    item.body,
    item.quoted,
    item.reason,
    ...(item.tags || []),
  ]
    .join(" ")
    .toLowerCase();
}

export function normalizeItems(items) {
  return items.map((item) => ({
    ...item,
    title: (item.title || "").trim(),
    body: (item.body || "").trim(),
    quoted: (item.quoted || "").trim(),
    reason: (item.reason || "").trim(),
  }));
}

export function filterItemsByQuery(items, query) {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) {
    return items;
  }

  return items.filter((item) => getSearchText(item).includes(normalizedQuery));
}

export function groupItemsByDay(items) {
  const grouped = new Map();

  for (const item of items) {
    const dayItems = grouped.get(item.day);

    if (dayItems) {
      dayItems.push(item);
      continue;
    }

    grouped.set(item.day, [item]);
  }

  return [...grouped.entries()];
}

export function getMediaThemeIndex(source, time, count) {
  return hashString(source + time) % count;
}

export function getAvatarThemeIndex(source, count) {
  return hashString(source) % count;
}

export function getTimelineItemKey(item) {
  return `${item.day}-${item.time}-${item.sourceId || item.source}-${item.link}-${item.title}`;
}
