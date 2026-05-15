import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export default function AboutPageAdmin() {
  const [config, setConfig] = useState({
    title: "",
    description: "",
    qr_code_url: "",
    follow_link: "",
    contact_info: "",
    links: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchAboutConfig();
  }, []);

  const fetchAboutConfig = async () => {
    try {
      const res = await fetch("/api/about");
      if (res.ok) {
        const data = await res.json();
        setConfig({
          title: data.title || "",
          description: data.description || "",
          qr_code_url: data.qr_code_url || "",
          follow_link: data.follow_link || "",
          contact_info: data.contact_info || "",
          links: data.links || [],
        });
      }
    } catch (error) {
      console.error("Failed to fetch about config:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field) => (event) => {
    setConfig((prev) => ({ ...prev, [field]: event.target.value }));
  };

  const handleLinkChange = (index, field) => (event) => {
    setConfig((prev) => {
      const links = [...prev.links];
      links[index] = { ...links[index], [field]: event.target.value };
      return { ...prev, links };
    });
  };

  const handleAddLink = () => {
    setConfig((prev) => ({
      ...prev,
      links: [...prev.links, { label: "", url: "" }],
    }));
  };

  const handleRemoveLink = (index) => {
    setConfig((prev) => ({
      ...prev,
      links: prev.links.filter((_, i) => i !== index),
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    try {
      const token = localStorage.getItem("admin_token");
      const res = await fetch("/api/admin/about", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(config),
      });

      if (res.ok) {
        setMessage({ type: "success", text: "保存成功" });
      } else {
        setMessage({ type: "error", text: "保存失败" });
      }
    } catch (error) {
      setMessage({ type: "error", text: "保存失败" });
    }

    setSaving(false);
  };

  if (loading) {
    return (
      <div className="admin-page">
        <p className="admin-page__loading">加载中...</p>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <h1 className="admin-page__title">关于页面</h1>
        <p className="admin-page__subtitle">编辑关于页面的微信公众号信息</p>
      </header>

      <div className="admin-form">
        <div className="admin-form__field">
          <label htmlFor="title">标题</label>
          <input
            id="title"
            type="text"
            value={config.title}
            onChange={handleChange("title")}
            placeholder="关注我们的微信公众号"
          />
        </div>

        <div className="admin-form__field">
          <label htmlFor="description">描述</label>
          <textarea
            id="description"
            value={config.description}
            onChange={handleChange("description")}
            placeholder="获取最新 AI 动态，深度解读技术趋势..."
            rows={4}
          />
        </div>

        <div className="admin-form__field">
          <label htmlFor="qr_code_url">二维码图片 URL</label>
          <input
            id="qr_code_url"
            type="text"
            value={config.qr_code_url}
            onChange={handleChange("qr_code_url")}
            placeholder="/wechat-qr.png"
          />
        </div>

        <div className="admin-form__field">
          <label>外部链接</label>
          <div className="admin-form__links">
            {config.links.map((link, index) => (
              <div key={index} className="admin-form__link-row">
                <input
                  type="text"
                  value={link.label}
                  onChange={handleLinkChange(index, "label")}
                  placeholder="链接名称"
                  className="admin-form__link-label"
                />
                <input
                  type="text"
                  value={link.url}
                  onChange={handleLinkChange(index, "url")}
                  placeholder="https://..."
                  className="admin-form__link-url"
                />
                <button
                  type="button"
                  className="admin-form__link-remove"
                  onClick={() => handleRemoveLink(index)}
                >
                  删除
                </button>
              </div>
            ))}
            <button
              type="button"
              className="admin-form__link-add"
              onClick={handleAddLink}
            >
              + 添加链接
            </button>
          </div>
        </div>

        <div className="admin-form__field">
          <label htmlFor="follow_link">关注链接（可选）</label>
          <input
            id="follow_link"
            type="text"
            value={config.follow_link}
            onChange={handleChange("follow_link")}
            placeholder="https://mp.weixin.qq.com/..."
          />
        </div>

        <div className="admin-form__field">
          <label htmlFor="contact_info">联系方式（可选）</label>
          <input
            id="contact_info"
            type="text"
            value={config.contact_info}
            onChange={handleChange("contact_info")}
            placeholder="邮箱: contact@example.com"
          />
        </div>

        {message && (
          <p className={`admin-form__message admin-form__message--${message.type}`}>
            {message.text}
          </p>
        )}

        <div className="admin-form__actions">
          <Link className="admin-page__button" to="/about" target="_blank">
            预览
          </Link>
          <button
            className="admin-form__submit"
            type="button"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "保存中..." : "保存更改"}
          </button>
        </div>
      </div>
    </div>
  );
}
