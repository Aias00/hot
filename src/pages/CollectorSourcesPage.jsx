import { useEffect, useMemo, useState } from "react";

import PageHeader from "../components/PageHeader";
import ErrorState from "../components/states/ErrorState";
import {
  createCollectorSource,
  deleteCollectorSource,
  executeCollector,
  fetchCollectorAdapterKinds,
  fetchCollectorRun,
  fetchCollectorRuns,
  fetchCollectorSources,
  updateCollectorSource,
} from "../data/collectRepository";
import { getSourceGroupMeta, groupSourcesForDisplay, listSourceGroups } from "../data/sourceCatalog";

const EMPTY_FORM = {
  source_id: "",
  adapter_kind: "rss-generic",
  title: "",
  description: "",
  enabled: true,
  base_url: "",
  seed_urls: "",
  config_json: "{}",
};

const COLLECTOR_GROUP_STORAGE_KEY = "collector-group-filter";

export default function CollectorSourcesPage() {
  const [adapters, setAdapters] = useState([]);
  const [sources, setSources] = useState([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [formState, setFormState] = useState(EMPTY_FORM);
  const [pageError, setPageError] = useState("");
  const [formError, setFormError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [runResults, setRunResults] = useState({});
  const [recentRuns, setRecentRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRunDetail, setSelectedRunDetail] = useState(null);
  const [busyKey, setBusyKey] = useState("");
  const [selectedGroupKey, setSelectedGroupKey] = useState(
    () => localStorage.getItem(COLLECTOR_GROUP_STORAGE_KEY) || "all",
  );

  async function loadData() {
    const [adapterPayload, sourcePayload, runPayload] = await Promise.all([
      fetchCollectorAdapterKinds(),
      fetchCollectorSources(),
      fetchCollectorRuns(),
    ]);
    setAdapters(adapterPayload.items || []);
    setSources(sourcePayload.items || []);
    setRecentRuns(runPayload.items || []);
  }

  useEffect(() => {
    let ignore = false;

    async function bootstrap() {
      try {
        await loadData();
        if (!ignore) {
          setPageError("");
        }
      } catch (error) {
        if (!ignore) {
          setPageError(error instanceof Error ? error.message : "加载采集源失败");
        }
      }
    }

    bootstrap();

    return () => {
      ignore = true;
    };
  }, []);

  const selectedSource = useMemo(
    () => sources.find((source) => source.source_id === selectedSourceId) || null,
    [selectedSourceId, sources],
  );
  const discoverDiagnostics = useMemo(() => {
    const events = selectedRunDetail?.events || [];
    const discoverEvent = events.find((event) => event.node === "discover_candidates");
    return discoverEvent?.payload || null;
  }, [selectedRunDetail]);
  const sourceGroups = useMemo(() => listSourceGroups(), []);
  const scopedSources = useMemo(
    () =>
      selectedGroupKey === "all"
        ? sources
        : sources.filter((source) => getSourceGroupMeta(source).key === selectedGroupKey),
    [selectedGroupKey, sources],
  );
  const groupedSources = useMemo(
    () => groupSourcesForDisplay(scopedSources),
    [scopedSources],
  );
  const scopedSourceIds = useMemo(
    () => new Set(scopedSources.map((source) => source.source_id)),
    [scopedSources],
  );
  const visibleRuns = useMemo(
    () =>
      selectedGroupKey === "all"
        ? recentRuns
        : recentRuns.filter((run) => scopedSourceIds.has(run.source_id)),
    [recentRuns, scopedSourceIds, selectedGroupKey],
  );

  useEffect(() => {
    localStorage.setItem(COLLECTOR_GROUP_STORAGE_KEY, selectedGroupKey);
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
    if (!selectedRunId) {
      return;
    }

    const stillVisible = visibleRuns.some((run) => run.run_id === selectedRunId);
    if (!stillVisible) {
      setSelectedRunId("");
      setSelectedRunDetail(null);
    }
  }, [selectedRunId, visibleRuns]);

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }

    let ignore = false;

    async function loadRunDetail() {
      try {
        const payload = await fetchCollectorRun(selectedRunId);
        if (!ignore) {
          setSelectedRunDetail(payload);
        }
      } catch {
        if (!ignore) {
          setSelectedRunDetail(null);
        }
      }
    }

    loadRunDetail();

    return () => {
      ignore = true;
    };
  }, [selectedRunId]);

  function resetForm() {
    setSelectedSourceId("");
    setFormState(EMPTY_FORM);
    setFormError("");
    setStatusMessage("");
  }

  function fillFormFromSource(source) {
    setSelectedSourceId(source.source_id);
    setFormState({
      source_id: source.source_id,
      adapter_kind: source.adapter_kind,
      title: source.title,
      description: source.description,
      enabled: source.enabled,
      base_url: source.base_url || "",
      seed_urls: (source.seed_urls || []).join("\n"),
      config_json: JSON.stringify(source.config_json || {}, null, 2),
    });
    setFormError("");
    setStatusMessage("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError("");
    setStatusMessage("");
    setBusyKey("save");

    try {
      const payload = {
        source_id: formState.source_id.trim(),
        adapter_kind: formState.adapter_kind,
        title: formState.title.trim(),
        description: formState.description.trim(),
        enabled: formState.enabled,
        base_url: formState.base_url.trim() || null,
        seed_urls: formState.seed_urls
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
        config_json: JSON.parse(formState.config_json || "{}"),
      };

      if (selectedSourceId) {
        await updateCollectorSource(selectedSourceId, payload);
        setStatusMessage(`已更新 ${selectedSourceId}`);
      } else {
        await createCollectorSource(payload);
        setStatusMessage(`已创建 ${payload.source_id}`);
      }

      await loadData();
      resetForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "保存采集源失败");
    } finally {
      setBusyKey("");
    }
  }

  async function handleDelete(sourceId) {
    setBusyKey(`delete:${sourceId}`);
    setStatusMessage("");
    try {
      await deleteCollectorSource(sourceId);
      await loadData();
      if (selectedSourceId === sourceId) {
        resetForm();
      }
      setStatusMessage(`已删除 ${sourceId}`);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "删除采集源失败");
    } finally {
      setBusyKey("");
    }
  }

  async function handleExecute(sourceId, dryRun) {
    const key = `execute:${sourceId}:${dryRun ? "dry" : "live"}`;
    setBusyKey(key);
    setStatusMessage("");
    try {
      const result = await executeCollector({
        source_id: sourceId,
        dry_run: dryRun,
        limit: 10,
      });
      setRunResults((current) => ({ ...current, [sourceId]: result }));
      const runPayload = await fetchCollectorRuns();
      setRecentRuns(runPayload.items || []);
      setSelectedRunId(result.run_id);
      setStatusMessage(
        `${sourceId} ${dryRun ? "演练" : "采集"}完成：发现 ${result.summary.discovered_count} 条`,
      );
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "执行采集失败");
    } finally {
      setBusyKey("");
    }
  }

  return (
    <section className="collector-page">
      <PageHeader
        title="采集管理"
        subtitle="当前只开放真实 RSS 源；先 Dry run 验证，再正式采集并检查运行诊断"
        metaPrimary={`${sources.length} 个 source`}
        metaSecondary={`${adapters.length} 种 adapter`}
      />

      {pageError ? <ErrorState message={pageError} /> : null}

      <section className="collector-overview-grid">
        <article className="card collector-overview-card">
          <div className="collector-card-kicker">来源分层筛选</div>
          <div className="collector-overview-list">
            <button
              className={`collector-stat-chip${selectedGroupKey === "all" ? " is-active" : ""}`}
              onClick={() => setSelectedGroupKey("all")}
              type="button"
            >
              <span>全部层级</span>
              <strong>{sources.length}</strong>
            </button>
            {sourceGroups.map((group) => {
              const count = sources.filter((source) => getSourceGroupMeta(source).key === group.key).length;
              return (
                <button
                  className={`collector-stat-chip${selectedGroupKey === group.key ? " is-active" : ""}`}
                  key={group.key}
                  onClick={() => setSelectedGroupKey(group.key)}
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
          <div className="info-card-kicker">Step 1</div>
          <h2 className="info-card-title">现在默认只保留真实 RSS 来源</h2>
          <p className="info-card-copy">
            右侧现在只保留 OpenAI、GitHub Blog、Hugging Face 这类明确有效的 RSS 源。通常先看现有来源配置，再决定要不要复制一份做自己的 RSS source。
          </p>
        </article>
        <article className="card info-card">
          <div className="info-card-kicker">Step 2</div>
          <h2 className="info-card-title">先 Dry run，再正式采集</h2>
          <p className="info-card-copy">
            `Dry run` 只跑发现、抓取和归一化，不写入数据库。确认结果合理之后，再点“正式采集”把内容写进 `hot_items`。
          </p>
        </article>
        <article className="card info-card">
          <div className="info-card-kicker">Step 3</div>
          <h2 className="info-card-title">重点看运行诊断，不只看成功/失败</h2>
          <p className="info-card-copy">
            运行详情里的 `discover_candidates` 会直接告诉你这次是 `html-table`、`snapshot-json-home-shell-fallback` 还是别的模式，方便判断远程源到底哪里坏了。
          </p>
        </article>
      </section>

      <div className="collector-layout">
        <section className="card collector-form-card">
          <div className="collector-card-kicker">
            {selectedSource ? "编辑来源" : "新建来源"}
          </div>
          <form className="collector-form" onSubmit={handleSubmit}>
            <label className="collector-field">
              <span>source_id</span>
              <input
                className="field"
                value={formState.source_id}
                disabled={Boolean(selectedSourceId)}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, source_id: event.target.value }))
                }
              />
            </label>

            <label className="collector-field">
              <span>adapter</span>
              <select
                className="field"
                value={formState.adapter_kind}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, adapter_kind: event.target.value }))
                }
              >
                {adapters.map((adapter) => (
                  <option key={adapter} value={adapter}>
                    {adapter}
                  </option>
                ))}
              </select>
            </label>

            <label className="collector-field">
              <span>标题</span>
              <input
                className="field"
                value={formState.title}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, title: event.target.value }))
                }
              />
            </label>

            <label className="collector-field">
              <span>描述</span>
              <textarea
                className="field collector-textarea"
                value={formState.description}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, description: event.target.value }))
                }
              />
            </label>

            <label className="collector-field">
              <span>base_url</span>
              <input
                className="field"
                value={formState.base_url}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, base_url: event.target.value }))
                }
              />
            </label>

            <label className="collector-field">
              <span>seed_urls</span>
              <textarea
                className="field collector-textarea collector-textarea-mono"
                value={formState.seed_urls}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, seed_urls: event.target.value }))
                }
              />
            </label>

            <label className="collector-field">
              <span>config_json</span>
              <textarea
                className="field collector-textarea collector-textarea-mono"
                value={formState.config_json}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, config_json: event.target.value }))
                }
              />
            </label>

            <label className="collector-checkbox">
              <input
                checked={formState.enabled}
                type="checkbox"
                onChange={(event) =>
                  setFormState((current) => ({ ...current, enabled: event.target.checked }))
                }
              />
              <span>启用来源</span>
            </label>

            <div className="page-actions">
              <button className="btn btn-primary page-action-link" disabled={busyKey === "save"} type="submit">
                {selectedSource ? "更新来源" : "创建来源"}
              </button>
              <button className="btn page-action-link collector-secondary-btn" onClick={resetForm} type="button">
                重置
              </button>
            </div>
          </form>

          {formError ? <p className="collector-error">{formError}</p> : null}
          {statusMessage ? <p className="collector-status">{statusMessage}</p> : null}
        </section>

        <section className="collector-side">
          <section className="card collector-runs-card">
            <div className="collector-card-kicker">最近运行 · {visibleRuns.length}</div>
            {visibleRuns.length ? (
              <div className="collector-run-list">
                {visibleRuns.map((run) => (
                  <button
                    className={`collector-run-item${run.run_id === selectedRunId ? " is-active" : ""}`}
                    key={run.run_id}
                    onClick={() => setSelectedRunId(run.run_id)}
                    type="button"
                  >
                    <strong>{run.source_id}</strong>
                    <span>{run.status}</span>
                    <span>{run.summary?.normalized_count ?? 0} normalized</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="collector-source-copy">当前层级暂时没有运行记录。</p>
            )}
          </section>

          <section className="card collector-runs-card">
            <div className="collector-card-kicker">运行详情</div>
            {selectedRunDetail?.run ? (
              <div className="collector-run-detail">
                <div className="collector-run-meta">
                  <strong>{selectedRunDetail.run.source_id}</strong>
                  <span>{selectedRunDetail.run.status}</span>
                </div>
                <pre className="collector-config-preview">
                  {JSON.stringify(selectedRunDetail.run.summary, null, 2)}
                </pre>
                {discoverDiagnostics ? (
                  <pre className="collector-config-preview">
                    {JSON.stringify(
                      {
                        source_modes: discoverDiagnostics.source_modes || {},
                        seed_urls: discoverDiagnostics.seed_urls || [],
                      },
                      null,
                      2,
                    )}
                  </pre>
                ) : null}
                <div className="collector-run-events">
                  {selectedRunDetail.events.map((event, index) => (
                    <div className="collector-run-event" key={`${event.created_at}-${index}`}>
                      <strong>{event.node}</strong>
                      <span>{event.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="collector-source-copy">选择一次运行查看事件和摘要。</p>
            )}
          </section>
        </section>

        <section className="collector-list">
          {groupedSources.map((group) => (
            <section className="collector-source-group" key={group.key}>
              <div className="collector-source-group-head">
                <div className="collector-card-kicker">
                  {group.label} · {group.items.length}
                </div>
                <p className="collector-source-copy">{group.description}</p>
              </div>
              <div className="collector-group-list">
                {group.items.map((source) => {
                  const runResult = runResults[source.source_id];
                  return (
                    <article className="card collector-source-card" key={source.source_id}>
                      <div className="collector-source-head">
                        <div>
                          <div className="collector-card-kicker">{source.adapter_kind}</div>
                          <h2 className="collector-source-title">{source.title}</h2>
                          <p className="collector-source-id">{source.source_id}</p>
                        </div>
                        <span className={`collector-source-state${source.enabled ? " is-enabled" : ""}`}>
                          {source.enabled ? "enabled" : "disabled"}
                        </span>
                      </div>

                      <p className="collector-source-copy">{source.description}</p>

                      {source.seed_urls?.length ? (
                        <div className="collector-seed-list">
                          {source.seed_urls.map((url) => (
                            <code className="collector-seed-item" key={url}>
                              {url}
                            </code>
                          ))}
                        </div>
                      ) : null}

                      {source.config_json && Object.keys(source.config_json).length ? (
                        <pre className="collector-config-preview">
                          {JSON.stringify(source.config_json, null, 2)}
                        </pre>
                      ) : null}

                      {runResult ? (
                        <div className="collector-run-summary">
                          <strong>最近执行</strong>
                          <span>
                            {runResult.status} · 发现 {runResult.summary.discovered_count} / 归一化{" "}
                            {runResult.summary.normalized_count}
                          </span>
                        </div>
                      ) : null}

                      <div className="page-actions">
                        <button
                          className="btn btn-primary page-action-link"
                          onClick={() => handleExecute(source.source_id, true)}
                          disabled={busyKey === `execute:${source.source_id}:dry`}
                          type="button"
                        >
                          Dry run
                        </button>
                        <button
                          className="btn btn-primary page-action-link"
                          onClick={() => handleExecute(source.source_id, false)}
                          disabled={busyKey === `execute:${source.source_id}:live`}
                          type="button"
                        >
                          正式采集
                        </button>
                        <button
                          className="btn page-action-link collector-secondary-btn"
                          onClick={() => fillFormFromSource(source)}
                          type="button"
                        >
                          编辑
                        </button>
                        <button
                          className="btn page-action-link collector-danger-btn"
                          onClick={() => handleDelete(source.source_id)}
                          disabled={busyKey === `delete:${source.source_id}`}
                          type="button"
                        >
                          删除
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
        </section>
      </div>
    </section>
  );
}
