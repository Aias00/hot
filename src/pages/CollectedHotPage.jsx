import { useEffect, useMemo, useRef, useState } from "react";

import PageHeader from "../components/PageHeader";
import ErrorState from "../components/states/ErrorState";
import { fetchCollectedItems } from "../data/collectedRepository";
import { fetchCollectorSources } from "../data/collectRepository";
import { getSourceGroupMeta, groupSourcesForDisplay, listSourceGroups } from "../data/sourceCatalog";

const COLLECTED_GROUP_STORAGE_KEY = "collected-group-filter";

export default function CollectedHotPage() {
  const [items, setItems] = useState([]);
  const [sources, setSources] = useState([]);
  const [query, setQuery] = useState("");
  const [selectedSourceIds, setSelectedSourceIds] = useState([]);
  const [selectedTag, setSelectedTag] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [sortField, setSortField] = useState("date");
  const [sortDirection, setSortDirection] = useState("desc");
  const [selectedGroupKey, setSelectedGroupKey] = useState(
    () => localStorage.getItem(COLLECTED_GROUP_STORAGE_KEY) || "all",
  );
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [facets, setFacets] = useState({ sources: [], tags: [] });
  const [pageError, setPageError] = useState("");
  const loadMoreRef = useRef(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const [itemPayload, sourcePayload] = await Promise.all([
          fetchCollectedItems({
            query,
            sourceIds: selectedSourceIds,
            tag: selectedTag,
            from: fromDate,
            to: toDate,
            sort: sortField,
            dir: sortDirection,
            page,
            limit: 24,
          }),
          fetchCollectorSources(),
        ]);
        if (!ignore) {
          setItems((current) =>
            page === 1 ? itemPayload.items || [] : current.concat(itemPayload.items || []),
          );
          setTotalCount(itemPayload.total_count || 0);
          setHasNext(Boolean(itemPayload.has_next));
          setFacets(itemPayload.facets || { sources: [], tags: [] });
          setSources(sourcePayload.items || []);
          setPageError("");
        }
      } catch (error) {
        if (!ignore) {
          setPageError(error instanceof Error ? error.message : "加载采集热点失败");
        }
      }
    }

    load();

    return () => {
      ignore = true;
    };
  }, [fromDate, page, query, selectedSourceIds, selectedTag, sortDirection, sortField, toDate]);

  useEffect(() => {
    setPage(1);
  }, [fromDate, query, selectedSourceIds, selectedTag, sortDirection, sortField, toDate]);

  useEffect(() => {
    if (!hasNext || !loadMoreRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) {
          return;
        }

        setPage((current) => current + 1);
      },
      { rootMargin: "220px 0px" },
    );

    observer.observe(loadMoreRef.current);

    return () => {
      observer.disconnect();
    };
  }, [hasNext]);

  const sourceGroups = useMemo(() => listSourceGroups(), []);
  const sourceOptions = useMemo(
    () => sources.filter((source) => source.enabled),
    [sources],
  );
  const visibleSourceOptions = useMemo(
    () =>
      selectedGroupKey === "all"
        ? sourceOptions
        : sourceOptions.filter((source) => getSourceGroupMeta(source).key === selectedGroupKey),
    [selectedGroupKey, sourceOptions],
  );
  const groupedSourceFacets = useMemo(() => {
    const sourceMap = new Map(
      sources.map((source) => [source.source_id, source]),
    );
    const grouped = new Map();

    for (const facet of facets.sources) {
      const source = sourceMap.get(facet.source_id) || {
        source_id: facet.source_id,
        title: facet.source_title,
      };
      const meta = getSourceGroupMeta(source);
      if (!grouped.has(meta.key)) {
        grouped.set(meta.key, { ...meta, items: [] });
      }
      grouped.get(meta.key).items.push(facet);
    }

    return groupSourcesForDisplay(
      [...grouped.values()].flatMap((group) =>
        group.items.map((facet) => ({
          source_id: facet.source_id,
          title: facet.source_title,
        })),
      ),
    ).map((group) => ({
      ...group,
      items: group.items.map((item) =>
        facets.sources.find((facet) => facet.source_id === item.source_id),
      ),
    }));
  }, [facets.sources, sources]);
  const groupedSourceOptions = useMemo(
    () => groupSourcesForDisplay(visibleSourceOptions),
    [visibleSourceOptions],
  );

  useEffect(() => {
    localStorage.setItem(COLLECTED_GROUP_STORAGE_KEY, selectedGroupKey);
  }, [selectedGroupKey]);

  useEffect(() => {
    if (selectedGroupKey === "all") {
      return;
    }

    const hasGroup = sourceGroups.some((group) => group.key === selectedGroupKey);
    if (!hasGroup) {
      setSelectedGroupKey("all");
    }
  }, [selectedGroupKey, sourceGroups]);

  useEffect(() => {
    if (selectedGroupKey === "all") {
      return;
    }

    setSelectedSourceIds((current) =>
      current.filter((sourceId) =>
        visibleSourceOptions.some((source) => source.source_id === sourceId),
      ),
    );
  }, [selectedGroupKey, visibleSourceOptions]);

  return (
    <section className="collector-page">
      <PageHeader
        title="采集归档"
        subtitle="仅展示 collector 入库结果，适合排查、回看和验证采集质量"
        metaPrimary={`${totalCount} 条内容`}
        metaSecondary={
          selectedSourceIds.length === 1
            ? selectedSourceIds[0]
            : selectedSourceIds.length > 1
              ? `${selectedSourceIds.length} 个来源`
              : "不含静态时间线"
        }
      >
        <div className="filter-toolbar">
          <input
            className="field field-grow"
            placeholder="搜索采集标题…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select
            className="field"
            value={selectedSourceIds[0] || ""}
            onChange={(event) =>
              setSelectedSourceIds(event.target.value ? [event.target.value] : [])
            }
          >
            <option value="">全部来源</option>
            {groupedSourceOptions.map((group) => (
              <optgroup key={group.key} label={group.label}>
                {group.items.map((source) => (
                  <option key={source.source_id} value={source.source_id}>
                    {source.title}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <input
            className="field"
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
          />
          <input
            className="field"
            type="date"
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
          />
          <select
            className="field"
            value={sortField}
            onChange={(event) => setSortField(event.target.value)}
          >
            <option value="date">按时间</option>
            <option value="source">按来源</option>
            <option value="title">按标题</option>
          </select>
          <select
            className="field"
            value={sortDirection}
            onChange={(event) => setSortDirection(event.target.value)}
          >
            <option value="desc">降序</option>
            <option value="asc">升序</option>
          </select>
        </div>
      </PageHeader>

      {pageError ? <ErrorState message={pageError} /> : null}

      <section className="collector-overview-grid">
        <article className="card collector-overview-card">
          <div className="collector-card-kicker">层级过滤</div>
          <div className="collector-overview-list">
                <button
                  className={`collector-stat-chip${selectedGroupKey === "all" ? " is-active" : ""}`}
                  onClick={() => {
                    setSelectedGroupKey("all");
                    setSelectedSourceIds([]);
                  }}
                  type="button"
                >
              <span>全部层级</span>
              <strong>{sourceOptions.length}</strong>
            </button>
            {sourceGroups.map((group) => {
              const count = sourceOptions.filter((source) => getSourceGroupMeta(source).key === group.key).length;
              return (
                <button
                  className={`collector-stat-chip${selectedGroupKey === group.key ? " is-active" : ""}`}
                  key={group.key}
                  onClick={() => {
                    setSelectedGroupKey(group.key);
                    setSelectedSourceIds([]);
                  }}
                  type="button"
                >
                  <span>{group.label}</span>
                  <strong>{count}</strong>
                </button>
              );
            })}
          </div>
        </article>
      </section>

      <section className="info-grid">
        <article className="card info-card">
          <div className="info-card-kicker">定位</div>
          <h2 className="info-card-title">这里只看采集结果，不混静态快照</h2>
          <p className="info-card-copy">
            `/collected` 只展示 `hot_items` 里的 collector 入库内容，适合排查采集是否成功、摘要是否干净、分类和热度分是否合理。
          </p>
        </article>
        <article className="card info-card">
          <div className="info-card-kicker">区别</div>
          <h2 className="info-card-title">`/all` 是合并时间线，`/collected` 是采集归档</h2>
          <p className="info-card-copy">
            `/all` 会把采集结果和旧静态时间线合并在一起浏览；这里则只保留采集内容本身，方便做质量检查和来源分析。
          </p>
        </article>
      </section>

      <section className="collector-overview-grid">
        <article className="card collector-overview-card">
          <div className="collector-card-kicker">来源分层</div>
          <div className="collector-group-stack">
            {groupedSourceFacets.map((group) => (
              <section className="collector-facet-group" key={group.key}>
                <h3 className="collector-facet-group-title">
                  {group.label} · {group.items.length}
                </h3>
                <div className="collector-overview-list">
                  {group.items.map((facet) => (
                    <button
                      className={`collector-stat-chip${selectedSourceIds.includes(facet.source_id) ? " is-active" : ""}`}
                      key={facet.source_id}
                      onClick={() =>
                        setSelectedSourceIds((current) =>
                          current.includes(facet.source_id)
                            ? current.filter((value) => value !== facet.source_id)
                            : current.concat(facet.source_id),
                        )
                      }
                      type="button"
                    >
                      <span>{facet.source_title}</span>
                      <strong>{facet.count}</strong>
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </article>

        <article className="card collector-overview-card">
          <div className="collector-card-kicker">热门标签</div>
          <div className="collector-overview-list">
            {facets.tags.slice(0, 18).map((facet) => (
              <button
                className={`collector-stat-chip${selectedTag === facet.tag ? " is-active" : ""}`}
                key={facet.tag}
                onClick={() =>
                  setSelectedTag((current) => (current === facet.tag ? "" : facet.tag))
                }
                type="button"
              >
                <span>{facet.tag}</span>
                <strong>{facet.count}</strong>
              </button>
            ))}
          </div>
        </article>
      </section>

      <section className="collector-hot-grid">
        {items.map((item) => (
          <article className="card collector-hot-card" key={`${item.source_id}-${item.external_id}`}>
            <div className="collector-card-kicker">{item.source_title}</div>
            <h2 className="collector-hot-title">
              <a href={item.canonical_url} target="_blank" rel="noreferrer">
                {item.title}
              </a>
            </h2>
            <p className="collector-hot-summary">{item.summary}</p>
            <div className="collector-hot-meta">
              <span>{item.author || item.source_title}</span>
              <span>{getSourceGroupMeta(item.source_id).label}</span>
              {item.source_category_label ? <span>{item.source_category_label}</span> : null}
              {item.hot_score ? <span>{item.hot_score} 分</span> : null}
              <span>{item.published_at || item.created_at}</span>
            </div>
            {item.tags?.length ? (
              <div className="timeline-tags">
                {item.tags.map((tag) => (
                  <span className="tag" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
            {item.reason ? <p className="timeline-reason-copy">{item.reason}</p> : null}
          </article>
        ))}
      </section>
      {hasNext ? (
        <div className="timeline-load-more" ref={loadMoreRef}>
          <button className="timeline-load-pill" onClick={() => setPage((current) => current + 1)} type="button">
            继续下拉，加载更多采集热点
          </button>
        </div>
      ) : null}
    </section>
  );
}
