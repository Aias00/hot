import { useEffect, useState } from "react";

import { useAuth } from "../../hooks/useAuth.jsx";

export default function SourcesPage() {
  const { authFetch } = useAuth();
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    source_id: "",
    adapter_kind: "rss-generic",
    title: "",
    description: "",
    enabled: true,
    base_url: "",
    seed_urls: "",
  });

  const loadSources = async () => {
    setLoading(true);
    try {
      const response = await authFetch("/api/admin/sources");
      const data = await response.json();
      setSources(data);
    } catch (error) {
      console.error("Failed to load sources:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSources();
  }, []);

  const resetForm = () => {
    setFormData({
      source_id: "",
      adapter_kind: "rss-generic",
      title: "",
      description: "",
      enabled: true,
      base_url: "",
      seed_urls: "",
    });
    setEditing(null);
    setShowForm(false);
  };

  const handleEdit = (source) => {
    setFormData({
      source_id: source.source_id,
      adapter_kind: source.adapter_kind,
      title: source.title,
      description: source.description || "",
      enabled: source.enabled,
      base_url: source.base_url || "",
      seed_urls: (source.seed_urls || []).join("\n"),
    });
    setEditing(source.source_id);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      source_id: formData.source_id,
      adapter_kind: formData.adapter_kind,
      title: formData.title,
      description: formData.description,
      enabled: formData.enabled,
      base_url: formData.base_url || null,
      seed_urls: formData.seed_urls
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean),
    };

    try {
      if (editing) {
        await authFetch(`/api/admin/sources/${editing}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        await authFetch("/api/admin/sources", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      resetForm();
      loadSources();
    } catch (error) {
      console.error("Failed to save source:", error);
    }
  };

  const handleToggle = async (sourceId) => {
    try {
      await authFetch(`/api/admin/sources/${sourceId}/toggle`, { method: "PATCH" });
      loadSources();
    } catch (error) {
      console.error("Failed to toggle source:", error);
    }
  };

  const handleDelete = async (sourceId) => {
    if (!window.confirm("确定要删除此采集源吗？")) return;
    try {
      await authFetch(`/api/admin/sources/${sourceId}`, { method: "DELETE" });
      loadSources();
    } catch (error) {
      console.error("Failed to delete source:", error);
    }
  };

  if (loading) {
    return <div className="admin-page">加载中...</div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-page__header">
        <h1 className="admin-page__title">采集源管理</h1>
        <button onClick={() => setShowForm(true)} className="admin-page__button">
          新增采集源
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="admin-form">
          <div className="admin-form__row">
            <div className="admin-form__field">
              <label>Source ID</label>
              <input
                type="text"
                value={formData.source_id}
                onChange={(e) => setFormData({ ...formData, source_id: e.target.value })}
                disabled={!!editing}
                required
              />
            </div>
            <div className="admin-form__field">
              <label>适配器类型</label>
              <select
                value={formData.adapter_kind}
                onChange={(e) => setFormData({ ...formData, adapter_kind: e.target.value })}
              >
                <option value="rss-generic">RSS Generic</option>
              </select>
            </div>
          </div>
          <div className="admin-form__field">
            <label>标题</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              required
            />
          </div>
          <div className="admin-form__field">
            <label>描述</label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
          <div className="admin-form__field">
            <label>Base URL</label>
            <input
              type="url"
              value={formData.base_url}
              onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
              placeholder="https://example.com"
            />
          </div>
          <div className="admin-form__field">
            <label>种子 URL（每行一个）</label>
            <textarea
              value={formData.seed_urls}
              onChange={(e) => setFormData({ ...formData, seed_urls: e.target.value })}
              rows={4}
              placeholder="https://example.com/feed.xml"
            />
          </div>
          <div className="admin-form__field">
            <label className="admin-form__checkbox">
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
              />
              启用
            </label>
          </div>
          <div className="admin-form__actions">
            <button type="submit" className="admin-form__submit">
              {editing ? "更新" : "创建"}
            </button>
            <button type="button" onClick={resetForm} className="admin-form__cancel">
              取消
            </button>
          </div>
        </form>
      )}

      <table className="admin-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>标题</th>
            <th>适配器</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.source_id}>
              <td className="admin-table__monospace">{source.source_id}</td>
              <td>{source.title}</td>
              <td>{source.adapter_kind}</td>
              <td>
                <button
                  onClick={() => handleToggle(source.source_id)}
                  className={`admin-table__toggle ${source.enabled ? "admin-table__toggle--on" : ""}`}
                >
                  {source.enabled ? "启用" : "禁用"}
                </button>
              </td>
              <td className="admin-table__actions">
                <button onClick={() => handleEdit(source)} className="admin-table__edit">
                  编辑
                </button>
                <button onClick={() => handleDelete(source.source_id)} className="admin-table__delete">
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
