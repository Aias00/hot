import { useEffect, useState } from "react";

import { useAuth } from "../../hooks/useAuth.jsx";

export default function NavHubPage() {
  const { authFetch } = useAuth();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingCategory, setEditingCategory] = useState(null);
  const [editingLink, setEditingLink] = useState(null);
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [showLinkForm, setShowLinkForm] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState(null);

  const [categoryForm, setCategoryForm] = useState({
    id: "",
    name: "",
    icon: "",
    color: "#7dd3fc",
    enabled: true,
  });

  const [linkForm, setLinkForm] = useState({
    category_id: "",
    title: "",
    url: "",
    description: "",
    enabled: true,
  });

  const loadCategories = async () => {
    setLoading(true);
    try {
      const response = await authFetch("/api/admin/nav-hub/categories");
      const data = await response.json();
      setCategories(data);
    } catch (error) {
      console.error("Failed to load categories:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategories();
  }, []);

  const resetCategoryForm = () => {
    setCategoryForm({ id: "", name: "", icon: "", color: "#7dd3fc", enabled: true });
    setEditingCategory(null);
    setShowCategoryForm(false);
  };

  const resetLinkForm = () => {
    setLinkForm({ category_id: "", title: "", url: "", description: "", enabled: true });
    setEditingLink(null);
    setShowLinkForm(false);
  };

  const handleEditCategory = (category) => {
    setCategoryForm({
      id: category.id,
      name: category.name,
      icon: category.icon,
      color: category.color,
      enabled: category.enabled,
    });
    setEditingCategory(category.id);
    setShowCategoryForm(true);
  };

  const handleEditLink = (link, categoryId) => {
    setLinkForm({
      id: link.id,
      category_id: categoryId,
      title: link.title,
      url: link.url,
      description: link.description,
      enabled: link.enabled,
    });
    setEditingLink(link.id);
    setShowLinkForm(true);
  };

  const handleSubmitCategory = async (e) => {
    e.preventDefault();
    try {
      if (editingCategory) {
        await authFetch(`/api/admin/nav-hub/categories/${editingCategory}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(categoryForm),
        });
      } else {
        await authFetch("/api/admin/nav-hub/categories", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(categoryForm),
        });
      }
      resetCategoryForm();
      loadCategories();
    } catch (error) {
      console.error("Failed to save category:", error);
    }
  };

  const handleSubmitLink = async (e) => {
    e.preventDefault();
    try {
      if (editingLink) {
        await authFetch(`/api/admin/nav-hub/links/${editingLink}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(linkForm),
        });
      } else {
        await authFetch("/api/admin/nav-hub/links", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(linkForm),
        });
      }
      resetLinkForm();
      loadCategories();
    } catch (error) {
      console.error("Failed to save link:", error);
    }
  };

  const handleToggleCategory = async (categoryId) => {
    try {
      await authFetch(`/api/admin/nav-hub/categories/${categoryId}/toggle`, { method: "PATCH" });
      loadCategories();
    } catch (error) {
      console.error("Failed to toggle category:", error);
    }
  };

  const handleDeleteCategory = async (categoryId) => {
    if (!window.confirm("确定要删除此分类及其所有链接吗？")) return;
    try {
      await authFetch(`/api/admin/nav-hub/categories/${categoryId}`, { method: "DELETE" });
      loadCategories();
    } catch (error) {
      console.error("Failed to delete category:", error);
    }
  };

  const handleDeleteLink = async (linkId) => {
    if (!window.confirm("确定要删除此链接吗？")) return;
    try {
      await authFetch(`/api/admin/nav-hub/links/${linkId}`, { method: "DELETE" });
      loadCategories();
    } catch (error) {
      console.error("Failed to delete link:", error);
    }
  };

  if (loading) {
    return <div className="admin-page">加载中...</div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-page__header">
        <h1 className="admin-page__title">导航中心管理</h1>
        <button onClick={() => setShowCategoryForm(true)} className="admin-page__button">
          新增分类
        </button>
      </div>

      {showCategoryForm && (
        <form onSubmit={handleSubmitCategory} className="admin-form">
          <div className="admin-form__row">
            <div className="admin-form__field admin-form__field--small">
              <label>ID</label>
              <input
                type="text"
                value={categoryForm.id}
                onChange={(e) => setCategoryForm({ ...categoryForm, id: e.target.value })}
                disabled={!!editingCategory}
                required
                placeholder="dev"
              />
            </div>
            <div className="admin-form__field">
              <label>名称</label>
              <input
                type="text"
                value={categoryForm.name}
                onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                required
                placeholder="开发工具"
              />
            </div>
            <div className="admin-form__field admin-form__field--small">
              <label>颜色</label>
              <input
                type="color"
                value={categoryForm.color}
                onChange={(e) => setCategoryForm({ ...categoryForm, color: e.target.value })}
              />
            </div>
          </div>
          <div className="admin-form__field">
            <label>图标 (SVG)</label>
            <textarea
              value={categoryForm.icon}
              onChange={(e) => setCategoryForm({ ...categoryForm, icon: e.target.value })}
              rows={3}
              placeholder='<svg viewBox="0 0 24 24">...</svg>'
            />
          </div>
          <div className="admin-form__field">
            <label className="admin-form__checkbox">
              <input
                type="checkbox"
                checked={categoryForm.enabled}
                onChange={(e) => setCategoryForm({ ...categoryForm, enabled: e.target.checked })}
              />
              启用
            </label>
          </div>
          <div className="admin-form__actions">
            <button type="submit" className="admin-form__submit">
              {editingCategory ? "更新" : "创建"}
            </button>
            <button type="button" onClick={resetCategoryForm} className="admin-form__cancel">
              取消
            </button>
          </div>
        </form>
      )}

      {showLinkForm && (
        <form onSubmit={handleSubmitLink} className="admin-form">
          <div className="admin-form__row">
            <div className="admin-form__field">
              <label>所属分类</label>
              <select
                value={linkForm.category_id}
                onChange={(e) => setLinkForm({ ...linkForm, category_id: e.target.value })}
                required
              >
                <option value="">选择分类</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="admin-form__field">
              <label>标题</label>
              <input
                type="text"
                value={linkForm.title}
                onChange={(e) => setLinkForm({ ...linkForm, title: e.target.value })}
                required
                placeholder="GitHub"
              />
            </div>
          </div>
          <div className="admin-form__field">
            <label>URL</label>
            <input
              type="url"
              value={linkForm.url}
              onChange={(e) => setLinkForm({ ...linkForm, url: e.target.value })}
              required
              placeholder="https://github.com"
            />
          </div>
          <div className="admin-form__field">
            <label>描述</label>
            <input
              type="text"
              value={linkForm.description}
              onChange={(e) => setLinkForm({ ...linkForm, description: e.target.value })}
              placeholder="代码托管与协作平台"
            />
          </div>
          <div className="admin-form__field">
            <label className="admin-form__checkbox">
              <input
                type="checkbox"
                checked={linkForm.enabled}
                onChange={(e) => setLinkForm({ ...linkForm, enabled: e.target.checked })}
              />
              启用
            </label>
          </div>
          <div className="admin-form__actions">
            <button type="submit" className="admin-form__submit">
              {editingLink ? "更新" : "创建"}
            </button>
            <button type="button" onClick={resetLinkForm} className="admin-form__cancel">
              取消
            </button>
          </div>
        </form>
      )}

      <div className="nav-hub-admin">
        {categories.length === 0 ? (
          <div className="nav-hub-admin__empty">
            暂无导航分类。你可以先新增分类，或等待默认导航种子初始化完成。
          </div>
        ) : categories.map((category) => (
          <div key={category.id} className="nav-hub-admin__category">
            <div
              className="nav-hub-admin__category-header"
              style={{ "--hub-accent": category.color }}
            >
              <div className="nav-hub-admin__category-info">
                <span
                  className="nav-hub-admin__category-icon"
                  dangerouslySetInnerHTML={{ __html: category.icon }}
                />
                <span className="nav-hub-admin__category-name">{category.name}</span>
                <span className="nav-hub-admin__category-count">{category.links.length} 链接</span>
              </div>
              <div className="nav-hub-admin__category-actions">
                <button
                  onClick={() => handleToggleCategory(category.id)}
                  className={`admin-table__toggle ${category.enabled ? "admin-table__toggle--on" : ""}`}
                >
                  {category.enabled ? "启用" : "禁用"}
                </button>
                <button onClick={() => handleEditCategory(category)} className="admin-table__edit">
                  编辑
                </button>
                <button
                  onClick={() => {
                    setLinkForm({ ...linkForm, category_id: category.id });
                    setShowLinkForm(true);
                  }}
                  className="admin-page__button"
                >
                  添加链接
                </button>
                <button onClick={() => handleDeleteCategory(category.id)} className="admin-table__delete">
                  删除
                </button>
                <button
                  onClick={() => setExpandedCategory(expandedCategory === category.id ? null : category.id)}
                  className="admin-table__edit"
                >
                  {expandedCategory === category.id ? "收起" : "展开"}
                </button>
              </div>
            </div>
            {expandedCategory === category.id && (
              <div className="nav-hub-admin__links">
                {category.links.length === 0 ? (
                  <div className="nav-hub-admin__empty">暂无链接</div>
                ) : (
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>标题</th>
                        <th>URL</th>
                        <th>描述</th>
                        <th>状态</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {category.links.map((link) => (
                        <tr key={link.id}>
                          <td>{link.title}</td>
                          <td className="admin-table__monospace">{link.url}</td>
                          <td>{link.description}</td>
                          <td>
                            <button
                              onClick={() => handleDeleteLink(link.id)}
                              className="admin-table__delete"
                            >
                              删除
                            </button>
                            <button
                              onClick={() => handleEditLink(link, category.id)}
                              className="admin-table__edit"
                            >
                              编辑
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
