import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import ErrorState from "../components/states/ErrorState";
import { useApiMpSnapshot } from "../hooks/useInfiniteMpSnapshot";

export default function MpPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentQuery = searchParams.get("q") || "";
  const currentSince = searchParams.get("since") || "30d";
  const currentPage = Number.parseInt(searchParams.get("page") || "1", 10) || 1;
  const [draftQuery, setDraftQuery] = useState(currentQuery);
  const loadMoreRef = useRef(null);
  const { snapshot, loadError, loadNextPage } = useApiMpSnapshot({
    query: currentQuery,
    since: currentSince,
    page: currentPage,
  });

  useEffect(() => {
    setDraftQuery(currentQuery);
  }, [currentQuery]);

  const filteredRows = useMemo(() => {
    if (!snapshot) {
      return [];
    }

    return snapshot.rows;
  }, [snapshot]);

  const activePagination = snapshot?.pagination ?? null;

  const visibleRows = useMemo(() => {
    if (!snapshot) {
      return [];
    }

    return filteredRows;
  }, [filteredRows, snapshot]);

  const pushPage = (nextPage) => {
    const next = new URLSearchParams(searchParams);

    if (nextPage <= 1) {
      next.delete("page");
    } else {
      next.set("page", String(nextPage));
    }

    setSearchParams(next);
  };

  const loadMore = async () => {
    await loadNextPage();
  };

  useEffect(() => {
    if (!activePagination?.hasNext || !loadMoreRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) {
          return;
        }

        loadMore();
      },
      { rootMargin: "180px 0px" },
    );

    observer.observe(loadMoreRef.current);

    return () => {
      observer.disconnect();
    };
  }, [activePagination?.currentPage, activePagination?.hasNext, loadMore]);

  if (!snapshot) {
    return null;
  }

  const rangeOptions =
    snapshot.filters?.options?.length
      ? snapshot.filters.options
      : [
          { label: "过去 24h", value: "24h" },
          { label: "过去 7 天", value: "7d" },
          { label: "过去 30 天", value: "30d" },
          { label: "过去 1 年", value: "365d" },
          { label: "全部", value: "all" },
        ];

  return (
    <section className="mp-page">
      {loadError ? <ErrorState message={loadError} /> : null}
      <header className="card mp-header">
        <div className="header-row">
          <div>
            <h1 className="page-title">{snapshot.title}</h1>
            <p className="page-subtitle">{snapshot.subtitle}</p>
          </div>
          <div className="page-meta">
            {snapshot.pageMeta.map((entry) => (
              <span key={entry}>{entry}</span>
            ))}
          </div>
        </div>

        <div className="divider page-divider"></div>

        <div className="mp-toolbar">
          <div className="mp-range-row">
            {rangeOptions.map((range) => (
              <button
                className={`mp-range-chip${range.value === currentSince ? " is-active" : ""}`}
                key={range.value}
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.set("since", range.value);
                  next.set("page", "1");
                  if (draftQuery.trim()) {
                    next.set("q", draftQuery.trim());
                  } else {
                    next.delete("q");
                  }
                  setSearchParams(next);
                }}
                type="button"
              >
                {range.label}
              </button>
            ))}
          </div>

          <form
            className="filter-toolbar"
            onSubmit={(event) => {
              event.preventDefault();
              const next = new URLSearchParams(searchParams);
              next.set("since", currentSince);
              next.set("page", "1");
              if (draftQuery.trim()) {
                next.set("q", draftQuery.trim());
              } else {
                next.delete("q");
              }
              setSearchParams(next);
            }}
          >
            <input
              className="field field-grow"
              placeholder="搜索爆文标题…"
              value={draftQuery}
              onChange={(event) => setDraftQuery(event.target.value)}
            />
            <button className="btn btn-primary btn-sm" type="submit">
              筛选
            </button>
          </form>
        </div>
      </header>

      <section className="card mp-table-shell">
        <table className="mp-table">
          <thead>
            <tr>
              <th>发文日期</th>
              <th>标题</th>
              <th>公众号</th>
              <th>阅读</th>
              <th>点赞</th>
              <th>转发</th>
              <th>异常值</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={`${row.date}-${row.title}`}>
                <td>{row.date}</td>
                <td className="mp-title-cell">
                  <a href={row.href} target="_blank" rel="noreferrer">
                    {row.title}
                  </a>
                </td>
                <td className="mp-account-col">
                  <div className="mp-account-sub">
                    <span>{row.account}</span>
                    {row.badge ? <span className="mp-badge-inline">{row.badge}</span> : null}
                  </div>
                </td>
                <td>{row.reads}</td>
                <td>{row.likes}</td>
                <td>{row.shares}</td>
                <td>
                  <span className="mp-outlier-pill">{row.outlier}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {activePagination ? (
        <nav className="mp-pagination" aria-label="分页">
          <button
            className={`mp-pagination-btn${activePagination.hasPrev ? "" : " is-disabled"}`}
            disabled={!activePagination.hasPrev}
            onClick={() => {
              if (!activePagination.hasPrev) {
                return;
              }

              pushPage(activePagination.prevPage);
            }}
            type="button"
          >
            ‹ 上一页
          </button>

          <div className="mp-pagination-pages">
            {activePagination.pages.map((entry) => (
              <button
                className={`mp-pagination-num${entry.current ? " is-current" : ""}`}
                key={entry.page}
                onClick={() => pushPage(entry.page)}
                type="button"
              >
                {entry.label}
              </button>
            ))}
          </div>

          <button
            className={`mp-pagination-btn${activePagination.hasNext ? "" : " is-disabled"}`}
            disabled={!activePagination.hasNext}
            onClick={() => {
              if (!activePagination.hasNext) {
                return;
              }

              pushPage(activePagination.nextPage);
            }}
            type="button"
          >
            下一页 ›
          </button>
        </nav>
      ) : null}

      {activePagination?.hasNext ? (
        <div className="timeline-load-more" ref={loadMoreRef}>
          <button className="timeline-load-pill" onClick={loadMore} type="button">
            继续下拉，自动加载第 {activePagination.nextPage} 页
          </button>
        </div>
      ) : null}
    </section>
  );
}
