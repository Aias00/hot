import { startTransition, useDeferredValue, useMemo, useState } from "react";

import PageHeader from "../components/PageHeader";
import SearchToolbar from "../components/SearchToolbar";
import ErrorState from "../components/states/ErrorState";
import Timeline from "../components/Timeline";
import { useInfiniteFeedItems } from "../hooks/useInfiniteFeedItems";
import { useInfiniteScrollTrigger } from "../hooks/useInfiniteScrollTrigger";
import { useProgressiveReveal } from "../hooks/useProgressiveReveal";
import { useApiFeedItems } from "../hooks/useUpstreamFeedItems";
import { filterItemsByQuery } from "../lib/feed";

export default function FeedPage({ page }) {
  const [query, setQuery] = useState("");
  const searchQuery = useDeferredValue(query);
  const isAllPage = page.path === "/all";
  const { items, loadError } = useApiFeedItems({ enabled: !isAllPage });
  const pagedFeed = useInfiniteFeedItems({
    enabled: isAllPage,
    query: searchQuery ?? query,
    pageSize: 12,
  });
  const scopedItems = useMemo(
    () => (page.filter ? items.filter(page.filter) : items),
    [items, page],
  );
  const filteredItems = useMemo(
    () => filterItemsByQuery(scopedItems, searchQuery ?? query),
    [query, scopedItems, searchQuery],
  );
  const { hasMore, loadMore, sentinelRef, visibleItems } = useProgressiveReveal(filteredItems, {
    enabled: page.progressiveReveal,
    batchSize: 5,
  });
  const feedSentinel = useInfiniteScrollTrigger({
    enabled: isAllPage,
    hasMore: pagedFeed.hasNext,
    isLoading: pagedFeed.isLoading,
    onLoadMore: pagedFeed.loadMore,
  });
  const timelineItems = isAllPage ? pagedFeed.items : visibleItems;
  const timelineHasMore = isAllPage ? pagedFeed.hasNext : hasMore;
  const timelineSentinelRef = isAllPage ? feedSentinel.sentinelRef : sentinelRef;
  const timelineLoadMore = isAllPage ? pagedFeed.loadMore : loadMore;
  const activeLoadError = isAllPage ? pagedFeed.loadError : loadError;

  return (
    <>
      <PageHeader
        title={page.title}
        subtitle={page.subtitle}
        metaPrimary={
          isAllPage ? null : `${filteredItems.length} 条结果`
        }
        metaSecondary={isAllPage ? null : page.metaSecondary || "静态设计 fork"}
      >
        <SearchToolbar
          query={query}
          onQueryChange={(nextValue) => {
            startTransition(() => {
              setQuery(nextValue);
            });
          }}
        />
      </PageHeader>

      {activeLoadError ? (
        <ErrorState message={activeLoadError} />
      ) : (
        <Timeline
          items={timelineItems}
          query={query}
          progressive={isAllPage || page.progressiveReveal}
          sentinelRef={timelineSentinelRef}
          hasMore={timelineHasMore}
          onLoadMore={timelineLoadMore}
        />
      )}
    </>
  );
}
