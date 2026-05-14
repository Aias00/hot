import { groupItemsByDay, getTimelineItemKey } from "../lib/feed";
import EmptyState from "./states/EmptyState";
import TimelineItem from "./TimelineItem";

export default function Timeline({
  items,
  query,
  progressive = false,
  sentinelRef,
  hasMore,
  onLoadMore,
}) {
  if (!items.length) {
    return <EmptyState query={query} />;
  }

  return (
    <section className="timeline" aria-live="polite">
      {groupItemsByDay(items).map(([day, dayItems]) => (
        <section className="timeline-day" key={day}>
          <div className="timeline-day-head">
            <div className="timeline-date">{day}</div>
          </div>
          <div className="timeline-day-items">
            {dayItems.map((item) => (
              <TimelineItem key={getTimelineItemKey(item)} item={item} />
            ))}
          </div>
        </section>
      ))}
      {progressive && hasMore ? (
        <div className="timeline-load-more" ref={sentinelRef}>
          <button className="timeline-load-pill" onClick={onLoadMore} type="button">
            继续下拉，自动加载 5 条
          </button>
        </div>
      ) : null}
    </section>
  );
}
