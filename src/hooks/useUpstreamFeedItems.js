import { useEffect, useState } from "react";

import { loadFeedSnapshot } from "../data/feedRepository";
import { normalizeItems } from "../lib/feed";

export function useApiFeedItems({ enabled = true } = {}) {
  const [items, setItems] = useState([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!enabled) {
      setItems([]);
      setLoadError("");
      return;
    }

    let ignore = false;

    async function loadItems() {
      try {
        const parsed = normalizeItems(await loadFeedSnapshot());

        if (ignore) {
          return;
        }

        setItems(parsed);
        setLoadError("");
      } catch (error) {
        try {
          const fallback = await loadFeedSnapshot();

          if (ignore) {
            return;
          }

          setItems(fallback);
          setLoadError("");
        } catch (fallbackError) {
          if (ignore) {
            return;
          }

          setLoadError(
            fallbackError instanceof Error ? fallbackError.message : "数据加载失败",
          );
        }
      }
    }

    loadItems();

    return () => {
      ignore = true;
    };
  }, [enabled]);

  return { items, loadError };
}
