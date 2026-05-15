import { useEffect, useState } from "react";

export default function AboutPage() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/about")
      .then((res) => res.json())
      .then((data) => {
        setConfig(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <section className="about-page">
        <div className="about-content">
          <p className="about-loading">加载中...</p>
        </div>
      </section>
    );
  }

  if (!config) {
    return (
      <section className="about-page">
        <div className="about-content">
          <p>暂无内容</p>
        </div>
      </section>
    );
  }

  return (
    <section className="about-page">
      <div className="about-bg" aria-hidden="true"></div>
      <div className="about-content">
        {config.qr_code_url && (
          <div className="about-qr-wrap">
            <img
              className="about-qr-image"
              src={config.qr_code_url}
              alt="微信公众号二维码"
            />
          </div>
        )}

        {config.title && <h1 className="about-title">{config.title}</h1>}

        {config.description && (
          <p className="about-description">{config.description}</p>
        )}

        {config.follow_link && (
          <a
            className="btn btn-primary about-follow-btn"
            href={config.follow_link}
            target="_blank"
            rel="noopener noreferrer"
          >
            关注公众号
          </a>
        )}

        {config.contact_info && (
          <p className="about-contact">{config.contact_info}</p>
        )}
      </div>
    </section>
  );
}
