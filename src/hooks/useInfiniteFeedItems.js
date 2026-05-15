import { useCallback, useEffect, useState } from "react";

import { loadFeedPage } from "../data/feedRepository";
import { normalizeItems } from "../lib/feed";

export function useInfiniteFeedItems({
  enabled = false,
  query = "",
  pageSize = 12,
} = {}) {
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!enabled) {
      return;
    }

    setPage(1);
  }, [enabled, query, pageSize]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let ignore = false;

    async function loadItems() {
      setIsLoading(true);
      try {
        const payload = await loadFeedPage({
          query,
          page,
          limit: pageSize,
        });
        const parsed = normalizeItems(payload.items || []);

        if (ignore) {
          return;
        }

        setItems((current) => (page === 1 ? parsed : current.concat(parsed)));
        setTotalCount(payload.total_count || 0);
        setHasNext(Boolean(payload.has_next));
        setLoadError("");
      } catch (error) {
        if (!ignore) {
          if (page === 1) {
            setItems([]);
          }
          setLoadError(error instanceof Error ? error.message : "数据加载失败");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    loadItems();

    return () => {
      ignore = true;
    };
  }, [enabled, page, pageSize, query]);

  const loadMore = useCallback(() => {
    if (!enabled || !hasNext || isLoading) {
      return;
    }

    setPage((current) => current + 1);
  }, [enabled, hasNext, isLoading]);

  return {
    items,
    totalCount,
    hasNext,
    isLoading,
    loadError,
    loadMore,
  };
}

