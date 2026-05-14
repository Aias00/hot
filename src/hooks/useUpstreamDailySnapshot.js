import { useEffect, useState } from "react";

import { fetchDailySnapshot } from "../data/dailyRepository";

export function useApiDailySnapshot(path) {
  const [snapshot, setSnapshot] = useState(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadSnapshot() {
      try {
        const parsed =
          path === "/daily/archive"
            ? await fetchDailySnapshot({ view: "archive" })
            : await fetchDailySnapshot({
                view: "issue",
                date: path === "/daily" ? "2026-05-08" : path.replace("/daily/", ""),
              });

        if (ignore) {
          return;
        }

        setSnapshot(parsed);
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
  }, [path]);

  return { snapshot, loadError };
}
