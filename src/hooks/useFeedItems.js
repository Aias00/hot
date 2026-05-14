import { useEffect, useState } from "react";

import { loadFeedSnapshot } from "../data/feedRepository";
import { normalizeItems } from "../lib/feed";

export function useFeedItems() {
  const [items, setItems] = useState([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadItems() {
      try {
        const payload = await loadFeedSnapshot();

        if (ignore) {
          return;
        }

        setItems(normalizeItems(payload));
        setLoadError("");
      } catch (error) {
        if (ignore) {
          return;
        }

        setLoadError(error instanceof Error ? error.message : "数据加载失败");
      }
    }

    loadItems();

    return () => {
      ignore = true;
    };
  }, []);

  return { items, loadError };
}
