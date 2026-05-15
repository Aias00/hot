import { useEffect, useState } from "react";

import { useAuth } from "../../hooks/useAuth.jsx";

export default function SchedulePage() {
  const { authFetch } = useAuth();
  const [schedule, setSchedule] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastRunResult, setLastRunResult] = useState(null);

  const [form, setForm] = useState({
    enabled: false,
    interval_minutes: 60,
  });

  const loadSchedule = async () => {
    setLoading(true);
    try {
      const response = await authFetch("/api/admin/schedule");
      const data = await response.json();
      setSchedule(data);
      setForm({
        enabled: data.enabled || false,
        interval_minutes: data.interval_minutes || 60,
      });
      if (data.last_run_status) {
        try {
          setLastRunResult(JSON.parse(data.last_run_status));
        } catch {
          setLastRunResult({ raw: data.last_run_status });
        }
      }
    } catch (error) {
      console.error("Failed to load schedule:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSchedule();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await authFetch("/api/admin/schedule", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await response.json();
      setSchedule(data);
    } catch (error) {
      console.error("Failed to save schedule:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    setLastRunResult(null);
    try {
      const response = await authFetch("/api/admin/schedule/run", {
        method: "POST",
      });
      const data = await response.json();
      setLastRunResult(data);
      loadSchedule();
    } catch (error) {
      console.error("Failed to run collection:", error);
      setLastRunResult({ error: String(error) });
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return <div className="admin-page">加载中...</div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-page__header">
        <h1 className="admin-page__title">定时采集配置</h1>
      </div>

      <div className="schedule-config">
        <div className="schedule-config__status">
          <div className="schedule-config__status-item">
            <span className="schedule-config__label">状态</span>
            <button
              className={`schedule-config__toggle ${schedule?.enabled ? "schedule-config__toggle--on" : ""}`}
              onClick={async () => {
                const newEnabled = !schedule?.enabled;
                setSaving(true);
                try {
                  const response = await authFetch("/api/admin/schedule", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ enabled: newEnabled, interval_minutes: form.interval_minutes }),
                  });
                  const data = await response.json();
                  setSchedule(data);
                  setForm({ ...form, enabled: data.enabled });
                } catch (error) {
                  console.error("Failed to toggle:", error);
                } finally {
                  setSaving(false);
                }
              }}
              disabled={saving}
            >
              {schedule?.enabled ? "已启用" : "已禁用"}
            </button>
          </div>
          {schedule?.next_run_at && (
            <div className="schedule-config__status-item">
              <span className="schedule-config__label">下次运行</span>
              <span className="schedule-config__value">
                {new Date(schedule.next_run_at).toLocaleString("zh-CN")}
              </span>
            </div>
          )}
          {schedule?.last_run_at && (
            <div className="schedule-config__status-item">
              <span className="schedule-config__label">上次运行</span>
              <span className="schedule-config__value">
                {new Date(schedule.last_run_at).toLocaleString("zh-CN")}
              </span>
            </div>
          )}
        </div>

        <form
          className="admin-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
        >
          <div className="admin-form__field">
            <label className="admin-form__checkbox">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              启用定时采集
            </label>
          </div>
          <div className="admin-form__field">
            <label>采集间隔（分钟）</label>
            <select
              value={form.interval_minutes}
              onChange={(e) => setForm({ ...form, interval_minutes: parseInt(e.target.value) })}
            >
              <option value={30}>30 分钟</option>
              <option value={60}>1 小时</option>
              <option value={120}>2 小时</option>
              <option value={360}>6 小时</option>
              <option value={720}>12 小时</option>
              <option value={1440}>24 小时</option>
            </select>
          </div>
          <div className="admin-form__actions">
            <button type="submit" className="admin-form__submit" disabled={saving}>
              {saving ? "保存中..." : "保存配置"}
            </button>
            <button
              type="button"
              className="admin-page__button"
              onClick={handleRunNow}
              disabled={running}
            >
              {running ? "采集中..." : "立即采集"}
            </button>
          </div>
        </form>

        {lastRunResult && (
          <div className="schedule-result">
            <h3 className="schedule-result__title">采集结果</h3>
            <div className="schedule-result__content">
              {lastRunResult.error ? (
                <div className="schedule-result__error">{lastRunResult.error}</div>
              ) : (
                <>
                  <div className="schedule-result__summary">
                    共采集 {lastRunResult.sources_count || 0} 个源
                  </div>
                  {lastRunResult.results && (
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Source ID</th>
                          <th>状态</th>
                          <th>采集数量</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lastRunResult.results.map((r, i) => (
                          <tr key={i}>
                            <td className="admin-table__monospace">{r.source_id}</td>
                            <td>
                              <span
                                className={`admin-table__toggle ${r.status === "completed" ? "admin-table__toggle--on" : ""}`}
                              >
                                {r.status}
                              </span>
                            </td>
                            <td>{r.persisted || r.error || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
