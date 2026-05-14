import { Link, useLocation } from "react-router-dom";

import { useProgressiveReveal } from "../hooks/useProgressiveReveal";
import ErrorState from "../components/states/ErrorState";
import { useApiDailySnapshot } from "../hooks/useUpstreamDailySnapshot";

function DailySidebar({ sidebar }) {
  if (!sidebar) {
    return null;
  }

  return (
    <aside className="daily-side-panel card">
      <nav className="daily-side-nav" aria-label="日报历史">
        {sidebar.latest ? (
          <Link className="daily-side-latest" to={sidebar.latest.href}>
            <span className="daily-side-latest-label">{sidebar.latest.label}</span>
            <span className="daily-side-latest-date">{sidebar.latest.date}</span>
          </Link>
        ) : null}

        <div className="daily-side-months">
          {sidebar.months.map((month) => (
            <details className="daily-side-month" key={month.month} open>
              <summary className="daily-side-month-head">
                <span className="daily-side-month-name">{month.month}</span>
                <span className="daily-side-month-count">{month.count}</span>
              </summary>
              <ul className="daily-side-day-list">
                {month.issues.map((issue) => (
                  <li key={`${month.month}-${issue.day}-${issue.href}`}>
                    <Link
                      className={`daily-side-day${issue.active ? " is-active" : ""}`}
                      to={issue.href}
                    >
                      <span className="daily-side-day-num">{issue.day}</span>
                      <span className="daily-side-day-headline">{issue.title}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </details>
          ))}
          <Link className="daily-side-archive" to={sidebar.archiveHref}>
            全部日报 →
          </Link>
        </div>
      </nav>
    </aside>
  );
}

function DailyIssueView({ snapshot }) {
  const {
    hasMore,
    loadMore,
    sentinelRef,
    visibleItems: visibleSections,
  } = useProgressiveReveal(snapshot.sections, {
    enabled: true,
    batchSize: 2,
  });

  return (
    <>
      <header className="card daily-masthead-card">
        <div className="daily-volume">{snapshot.masthead.eyebrow}</div>
        <h1>{snapshot.masthead.title}</h1>
        <div className="daily-masthead-meta-row">
          <span>{snapshot.masthead.date}</span>
          <span>{snapshot.masthead.tagline}</span>
        </div>
      </header>

      <div className="daily-sections">
        {visibleSections.map((section) => (
          <section className="card daily-section" key={section.number}>
            <div className="daily-section-head">
              <div className="daily-section-number">{section.number}</div>
              <div>
                <h2>{section.title}</h2>
                <div className="daily-section-english">{section.english}</div>
              </div>
              <div className="daily-section-count">{section.count} 篇</div>
            </div>

            <div className="daily-story-list">
              {section.stories.map((story) => (
                <article className="daily-story" key={story.title}>
                  <h3>
                    <a href={story.href} target="_blank" rel="noreferrer">
                      {story.title}
                    </a>
                  </h3>
                  <div className="daily-story-source">
                    {story.sourceRole ? (
                      <span className="daily-role-tag">{story.sourceRole}</span>
                    ) : null}
                    <span>{story.source}</span>
                  </div>
                  <p>{story.summary}</p>
                </article>
              ))}
            </div>
          </section>
        ))}
        {hasMore ? (
          <div className="timeline-load-more" ref={sentinelRef}>
            <button className="timeline-load-pill" onClick={loadMore} type="button">
              继续下拉，自动加载更多日报章节
            </button>
          </div>
        ) : null}
      </div>
    </>
  );
}

function DailyArchiveView({ snapshot }) {
  const {
    hasMore,
    loadMore,
    sentinelRef,
    visibleItems: visibleEntries,
  } = useProgressiveReveal(snapshot.archive.entries, {
    enabled: true,
    batchSize: 8,
  });

  return (
    <section className="card daily-archive-index">
      <div className="daily-volume">历史归档</div>
      <h1>{snapshot.archive.title}</h1>
      <div className="daily-section-english">{snapshot.archive.subtitle}</div>

      <div className="daily-index-list">
        {visibleEntries.map((entry) => (
          <Link className="daily-index-row" key={entry.href} to={entry.href}>
            <span className="daily-index-date">{entry.date}</span>
            <span className="daily-index-headline">{entry.headline}</span>
            <span className="daily-index-events">{entry.events}</span>
          </Link>
        ))}
      </div>
      {hasMore ? (
        <div className="timeline-load-more" ref={sentinelRef}>
          <button className="timeline-load-pill" onClick={loadMore} type="button">
            继续下拉，自动加载更多归档
          </button>
        </div>
      ) : null}
    </section>
  );
}

export default function DailyPage() {
  const location = useLocation();
  const { snapshot, loadError } = useApiDailySnapshot(location.pathname);

  if (!snapshot) {
    return null;
  }

  return (
    <section className="daily-page">
      <div className="daily-layout-shell">
        <DailySidebar sidebar={snapshot.sidebar} />

        <div className="daily-main-shell">
          {loadError ? <ErrorState message={loadError} /> : null}
          {snapshot.mode === "archive" ? (
            <DailyArchiveView snapshot={snapshot} />
          ) : (
            <DailyIssueView snapshot={snapshot} />
          )}
        </div>
      </div>
    </section>
  );
}
