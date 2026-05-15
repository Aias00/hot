import { useCallback, useEffect, useRef } from "react";

export function useInfiniteScrollTrigger({
  enabled = false,
  hasMore = false,
  isLoading = false,
  onLoadMore,
} = {}) {
  const sentinelRef = useRef(null);
  const pendingRef = useRef(false);

  useEffect(() => {
    if (!isLoading) {
      pendingRef.current = false;
    }
  }, [isLoading]);

  const triggerLoadMore = useCallback(() => {
    if (!enabled || !hasMore || isLoading || pendingRef.current) {
      return;
    }

    pendingRef.current = true;
    onLoadMore?.();
  }, [enabled, hasMore, isLoading, onLoadMore]);

  useEffect(() => {
    if (
      !enabled ||
      !hasMore ||
      !sentinelRef.current ||
      typeof IntersectionObserver === "undefined"
    ) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) {
          return;
        }

        triggerLoadMore();
      },
      { rootMargin: "220px 0px" },
    );

    observer.observe(sentinelRef.current);

    return () => {
      observer.disconnect();
    };
  }, [enabled, hasMore, triggerLoadMore]);

  useEffect(() => {
    if (!enabled || !hasMore) {
      return;
    }

    function onScroll() {
      const scrollBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 180;

      if (!scrollBottom) {
        return;
      }

      triggerLoadMore();
    }

    window.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScroll);
    };
  }, [enabled, hasMore, triggerLoadMore]);

  return { sentinelRef };
}
