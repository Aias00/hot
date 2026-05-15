import { useEffect, useState } from "react";

import { useAuth } from "../../hooks/useAuth.jsx";

export default function NavigationPage() {
  const { authFetch } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    icon: "",
    label: "",
    to: "",
    enabled: true,
  });

  const loadItems = async () => {
    setLoading(true);
    try {
      const response = await authFetch("/api/admin/navigation");
      const data = await response.json();
      setItems(data);
    } catch (error) {
      console.error("Failed to load navigation items:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, []);

  const resetForm = () => {
    setFormData({ icon: "", label: "", to: "", enabled: true });
    setEditing(null);
    setShowForm(false);
  };

  const handleEdit = (item) => {
    setFormData({
      icon: item.icon || "",
      label: item.label,
      to: item.to,
      enabled: item.enabled,
    });
    setEditing(item.id);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      icon: formData.icon,
      label: formData.label,
      to: formData.to,
      enabled: formData.enabled,
    };

    try {
      if (editing) {
        await authFetch(`/api/admin/navigation/${editing}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        await authFetch("/api/admin/navigation", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      resetForm();
      loadItems();
    } catch (error) {
      console.error("Failed to save navigation item:", error);
    }
  };

  const handleToggle = async (itemId) => {
    try {
      await authFetch(`/api/admin/navigation/${itemId}/toggle`, { method: "PATCH" });
      loadItems();
    } catch (error) {
      console.error("Failed to toggle navigation item:", error);
    }
  };

  const handleDelete = async (itemId) => {
    if (!window.confirm("确定要删除此导航项吗？")) return;
    try {
      await authFetch(`/api/admin/navigation/${itemId}`, { method: "DELETE" });
      loadItems();
    } catch (error) {
      console.error("Failed to delete navigation item:", error);
    }
  };

  const handleMoveUp = async (index) => {
    if (index === 0) return;
    const newItems = [...items];
    [newItems[index - 1], newItems[index]] = [newItems[index], newItems[index - 1]];
    const reorderData = newItems.map((item, i) => ({ id: item.id, sort_order: i }));
    try {
      await authFetch("/api/admin/navigation/reorder", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reorderData),
      });
      loadItems();
    } catch (error) {
      console.error("Failed to reorder navigation items:", error);
    }
  };

  const handleMoveDown = async (index) => {
    if (index === items.length - 1) return;
    const newItems = [...items];
    [newItems[index], newItems[index + 1]] = [newItems[index + 1], newItems[index]];
    const reorderData = newItems.map((item, i) => ({ id: item.id, sort_order: i }));
    try {
      await authFetch("/api/admin/navigation/reorder", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reorderData),
      });
      loadItems();
    } catch (error) {
      console.error("Failed to reorder navigation items:", error);
    }
  };

  if (loading) {
    return <div className="admin-page">加载中...</div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-page__header">
        <h1 className="admin-page__title">导航链接管理</h1>
        <button onClick={() => setShowForm(true)} className="admin-page__button">
          新增导航项
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="admin-form">
          <div className="admin-form__row">
            <div className="admin-form__field admin-form__field--small">
              <label>图标</label>
              <input
                type="text"
                value={formData.icon}
                onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                placeholder="☰"
              />
            </div>
            <div className="admin-form__field">
              <label>标签</label>
              <input
                type="text"
                value={formData.label}
                onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                required
              />
            </div>
            <div className="admin-form__field">
              <label>路径</label>
              <input
                type="text"
                value={formData.to}
                onChange={(e) => setFormData({ ...formData, to: e.target.value })}
                placeholder="/path"
                required
              />
            </div>
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
            <th>排序</th>
            <th>图标</th>
            <th>标签</th>
            <th>路径</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={item.id}>
              <td className="admin-table__sort">
                <button
                  onClick={() => handleMoveUp(index)}
                  disabled={index === 0}
                  className="admin-table__sort-btn"
                >
                  ↑
                </button>
                <button
                  onClick={() => handleMoveDown(index)}
                  disabled={index === items.length - 1}
                  className="admin-table__sort-btn"
                >
                  ↓
                </button>
              </td>
              <td className="admin-table__icon">{item.icon}</td>
              <td>{item.label}</td>
              <td className="admin-table__monospace">{item.to}</td>
              <td>
                <button
                  onClick={() => handleToggle(item.id)}
                  className={`admin-table__toggle ${item.enabled ? "admin-table__toggle--on" : ""}`}
                >
                  {item.enabled ? "启用" : "禁用"}
                </button>
              </td>
              <td className="admin-table__actions">
                <button onClick={() => handleEdit(item)} className="admin-table__edit">
                  编辑
                </button>
                <button onClick={() => handleDelete(item.id)} className="admin-table__delete">
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
