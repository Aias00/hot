import { Link } from "react-router-dom";

import PageHeader from "../components/PageHeader";

export default function InfoPage({ page }) {
  return (
    <>
      <PageHeader
        title={page.title}
        subtitle={page.subtitle}
        metaSecondary={page.metaSecondary}
      />

      <section className="info-grid">
        {page.sections.map((section) => (
          <article className="card info-card" key={section.title}>
            <div className="info-card-kicker">{section.kicker}</div>
            <h2 className="info-card-title">{section.title}</h2>
            <p className="info-card-copy">{section.copy}</p>
            {section.tags?.length ? (
              <div className="timeline-tags">
                {section.tags.map((tag) => (
                  <span className="tag" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
            {section.actions?.length ? (
              <div className="page-actions">
                {section.actions.map((action) => (
                  action.external ? (
                    <a
                      className="btn btn-primary page-action-link"
                      href={action.href}
                      key={action.label}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {action.label}
                    </a>
                  ) : (
                    <Link
                      className="btn btn-primary page-action-link"
                      key={action.label}
                      to={action.to}
                    >
                      {action.label}
                    </Link>
                  )
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </>
  );
}
