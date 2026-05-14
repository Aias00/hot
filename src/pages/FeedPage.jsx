import { startTransition, useDeferredValue, useMemo, useState } from "react";

import PageHeader from "../components/PageHeader";
import SearchToolbar from "../components/SearchToolbar";
import ErrorState from "../components/states/ErrorState";
import Timeline from "../components/Timeline";
import { useProgressiveReveal } from "../hooks/useProgressiveReveal";
import { useApiFeedItems } from "../hooks/useUpstreamFeedItems";
import { filterItemsByQuery } from "../lib/feed";

export default function FeedPage({ page }) {
  const [query, setQuery] = useState("");
  const searchQuery = useDeferredValue(query);
  const { items, loadError } = useApiFeedItems();
  const isAllPage = page.path === "/all";
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

  return (
    <>
      <PageHeader
        title={page.title}
        subtitle={page.subtitle}
        metaPrimary={isAllPage ? null : `${filteredItems.length} 条结果`}
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

      {loadError ? (
        <ErrorState message={loadError} />
      ) : (
        <Timeline
          items={visibleItems}
          query={query}
          progressive={page.progressiveReveal}
          sentinelRef={sentinelRef}
          hasMore={hasMore}
          onLoadMore={loadMore}
        />
      )}
    </>
  );
}
