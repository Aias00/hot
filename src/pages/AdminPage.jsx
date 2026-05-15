import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export default function AdminPage() {
  const [config, setConfig] = useState({
    title: "",
    description: "",
    qr_code_url: "",
    follow_link: "",
    contact_info: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetch("/api/about")
      .then((res) => res.json())
      .then((data) => {
        setConfig(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleChange = (field) => (event) => {
    setConfig((prev) => ({ ...prev, [field]: event.target.value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    try {
      const res = await fetch("/api/admin/about", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (res.ok) {
        setMessage({ type: "success", text: "保存成功" });
      } else {
        setMessage({ type: "error", text: "保存失败" });
      }
    } catch {
      setMessage({ type: "error", text: "保存失败" });
    }

    setSaving(false);
  };

  if (loading) {
    return (
      <section className="admin-page">
        <PageHeader />
        <p className="admin-loading">加载中...</p>
      </section>
    );
  }

  return (
    <section className="admin-page">
      <PageHeader />

      <div className="admin-form">
        <div className="admin-field">
          <label className="admin-label" htmlFor="title">
            标题
          </label>
          <input
            id="title"
            className="admin-input"
            type="text"
            value={config.title}
            onChange={handleChange("title")}
            placeholder="关注我们的微信公众号"
          />
        </div>

        <div className="admin-field">
          <label className="admin-label" htmlFor="description">
            描述
          </label>
          <textarea
            id="description"
            className="admin-input admin-textarea"
            value={config.description}
            onChange={handleChange("description")}
            placeholder="获取最新 AI 动态，深度解读技术趋势..."
            rows={4}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label" htmlFor="qr_code_url">
            二维码图片 URL
          </label>
          <input
            id="qr_code_url"
            className="admin-input"
            type="text"
            value={config.qr_code_url}
            onChange={handleChange("qr_code_url")}
            placeholder="/wechat-qr.png"
          />
        </div>

        <div className="admin-field">
          <label className="admin-label" htmlFor="follow_link">
            关注链接（可选）
          </label>
          <input
            id="follow_link"
            className="admin-input"
            type="text"
            value={config.follow_link}
            onChange={handleChange("follow_link")}
            placeholder="https://mp.weixin.qq.com/..."
          />
        </div>

        <div className="admin-field">
          <label className="admin-label" htmlFor="contact_info">
            联系方式（可选）
          </label>
          <input
            id="contact_info"
            className="admin-input"
            type="text"
            value={config.contact_info}
            onChange={handleChange("contact_info")}
            placeholder="邮箱: contact@example.com"
          />
        </div>

        {message && (
          <p className={`admin-message admin-message-${message.type}`}>
            {message.text}
          </p>
        )}

        <div className="admin-actions">
          <Link className="btn btn-secondary" to="/about">
            预览
          </Link>
          <button
            className="btn btn-primary"
            type="button"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "保存中..." : "保存更改"}
          </button>
        </div>
      </div>
    </section>
  );
}

function PageHeader() {
  return (
    <header className="admin-header">
      <h1 className="admin-title">管理后台</h1>
      <p className="admin-subtitle">编辑关于页面内容</p>
    </header>
  );
}
