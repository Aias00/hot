import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchMpSnapshot } from "../data/mpRepository";

export function useApiMpSnapshot({ query = "", since = "30d", page = "1" } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [accumulatedRows, setAccumulatedRows] = useState([]);
  const [loadError, setLoadError] = useState("");
  const [isLoadingNextPage, setIsLoadingNextPage] = useState(false);

  useEffect(() => {
    let ignore = false;

    async function loadSnapshot() {
      try {
        const parsed = await fetchMpSnapshot({ query, since, page });

        if (ignore) {
          return;
        }

        setSnapshot(parsed);
        setAccumulatedRows(parsed.rows);
        setLoadError("");
      } catch (error) {
        if (!ignore) {
          setLoadError(error instanceof Error ? error.message : "数据加载失败");
        }
      }
    }

    loadSnapshot();

    return () => {
      ignore = true;
    };
  }, [page, query, since]);

  const loadNextPage = useCallback(async () => {
    if (!snapshot?.pagination?.hasNext || isLoadingNextPage) {
      return;
    }

    setIsLoadingNextPage(true);

    try {
      const parsed = await fetchMpSnapshot({
        query,
        since,
        page: snapshot.pagination.nextPage,
      });

      setSnapshot(parsed);
      setAccumulatedRows((current) => current.concat(parsed.rows));
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "数据加载失败");
    } finally {
      setIsLoadingNextPage(false);
    }
  }, [isLoadingNextPage, query, since, snapshot]);

  const hydratedSnapshot = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    const subtitle = snapshot.subtitle.replace(
      /本页\s*\d+\s*条/,
      `已加载 ${accumulatedRows.length} 条`,
    );

    return {
      ...snapshot,
      subtitle,
      rows: accumulatedRows,
    };
  }, [accumulatedRows, snapshot]);

  return {
    snapshot: hydratedSnapshot,
    loadError,
    isLoadingNextPage,
    loadNextPage,
  };
}
