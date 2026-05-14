import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export function useProgressiveReveal(items, { enabled, batchSize = 5 } = {}) {
  const [visibleCount, setVisibleCount] = useState(
    enabled ? Math.min(batchSize, items.length) : items.length,
  );
  const sentinelRef = useRef(null);
  const loadLockedRef = useRef(false);

  const loadMore = useCallback(() => {
    if (!enabled || loadLockedRef.current) {
      return;
    }

    loadLockedRef.current = true;
    setVisibleCount((current) => Math.min(current + batchSize, items.length));

    queueMicrotask(() => {
      loadLockedRef.current = false;
    });
  }, [batchSize, enabled, items.length]);

  useEffect(() => {
    setVisibleCount(enabled ? Math.min(batchSize, items.length) : items.length);
  }, [batchSize, enabled, items.length]);

  useEffect(() => {
    if (!enabled || visibleCount >= items.length || !sentinelRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) {
          return;
        }

        loadMore();
      },
      { rootMargin: "220px 0px" },
    );

    observer.observe(sentinelRef.current);

    return () => {
      observer.disconnect();
    };
  }, [enabled, items.length, loadMore, visibleCount]);

  useEffect(() => {
    if (!enabled || visibleCount >= items.length) {
      return;
    }

    function onScroll() {
      const scrollBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 180;

      if (!scrollBottom) {
        return;
      }

      loadMore();
    }

    window.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScroll);
    };
  }, [enabled, items.length, loadMore, visibleCount]);

  const visibleItems = useMemo(() => {
    if (!enabled) {
      return items;
    }

    return items.slice(0, visibleCount);
  }, [enabled, items, visibleCount]);

  return {
    hasMore: enabled && visibleCount < items.length,
    loadMore,
    sentinelRef,
    visibleCount,
    visibleItems,
  };
}
