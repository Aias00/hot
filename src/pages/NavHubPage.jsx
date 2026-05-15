import { useMemo, useState } from "react";

import { navHubCategories } from "../data/navHubLinks";

export default function NavHubPage() {
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState(null);

  const filteredCategories = useMemo(() => {
    const query = search.toLowerCase().trim();
    if (!query && !activeCategory) {
      return navHubCategories;
    }

    return navHubCategories
      .filter((category) => !activeCategory || category.id === activeCategory)
      .map((category) => ({
        ...category,
        links: query
          ? category.links.filter(
              (link) =>
                link.title.toLowerCase().includes(query) ||
                link.description.toLowerCase().includes(query),
            )
          : category.links,
      }))
      .filter((category) => category.links.length > 0);
  }, [activeCategory, search]);

  const hour = new Date().getHours();
  const greeting =
    hour < 6 ? "夜深了" : hour < 12 ? "早上好" : hour < 18 ? "下午好" : "晚上好";

  return (
    <section className="nav-hub-page">
      <div className="nav-hub-bg nav-hub-grid" aria-hidden="true"></div>
      <div className="nav-hub-bg nav-hub-glow" aria-hidden="true"></div>

      <div className="nav-hub-wrap">
        <header className="nav-hub-header">
          <div className="nav-hub-greeting">
            <img className="nav-hub-brand" src="/logo-wordmark.svg" alt="AIHOT" />
            <span className="nav-hub-eyebrow">/ {greeting}</span>
            <h1 className="nav-hub-title">导航中心</h1>
          </div>

          <div className="nav-hub-search-wrap">
            <div className="nav-hub-search-box">
              <svg className="nav-hub-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.35-4.35" />
              </svg>
              <input
                className="nav-hub-search-input"
                type="text"
                placeholder="搜索链接..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              {search ? (
                <button className="nav-hub-search-clear" onClick={() => setSearch("")} type="button">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              ) : null}
            </div>
          </div>

          <nav className="nav-hub-filter">
            <button
              className={`nav-hub-pill ${activeCategory === null ? "is-active" : ""}`}
              onClick={() => setActiveCategory(null)}
              type="button"
            >
              全部
            </button>
            {navHubCategories.map((category) => (
              <button
                key={category.id}
                className={`nav-hub-pill ${activeCategory === category.id ? "is-active" : ""}`}
                onClick={() =>
                  setActiveCategory(activeCategory === category.id ? null : category.id)
                }
                style={{ "--hub-accent": category.color }}
                type="button"
              >
                {category.name}
              </button>
            ))}
          </nav>
        </header>

        <main className="nav-hub-grid-list">
          {filteredCategories.length === 0 ? (
            <div className="nav-hub-empty">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.35-4.35" />
              </svg>
              <p>没有找到匹配的结果</p>
              <span>换个关键词试试。</span>
            </div>
          ) : (
            filteredCategories.map((category) => (
              <section
                key={category.id}
                className="nav-hub-card"
                style={{ "--hub-accent": category.color }}
              >
                <div className="nav-hub-card-head">
                  <div
                    className="nav-hub-card-icon"
                    dangerouslySetInnerHTML={{ __html: category.icon }}
                  ></div>
                  <h2 className="nav-hub-card-title">{category.name}</h2>
                  <span className="nav-hub-card-count">{category.links.length}</span>
                </div>

                <ul className="nav-hub-link-list">
                  {category.links.map((link) => (
                    <li key={link.url}>
                      <a
                        className="nav-hub-link"
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <span className="nav-hub-link-dot"></span>
                        <span className="nav-hub-link-body">
                          <span className="nav-hub-link-title">{link.title}</span>
                          <span className="nav-hub-link-desc">{link.description}</span>
                        </span>
                        <svg className="nav-hub-link-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M7 17 17 7M7 7h10v10" />
                        </svg>
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </main>

        <footer className="nav-hub-footer">
          <span>导航中心 · {new Date().getFullYear()}</span>
        </footer>
      </div>
    </section>
  );
}
