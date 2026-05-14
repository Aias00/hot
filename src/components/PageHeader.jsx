export default function PageHeader({
  title,
  subtitle,
  metaPrimary,
  metaSecondary,
  children,
}) {
  return (
    <section className="card page-header">
      <div className="header-row">
        <div>
          <h1 className="page-title">{title}</h1>
          <p className="page-subtitle">{subtitle}</p>
        </div>
        {(metaPrimary || metaSecondary) && (
          <p className="page-meta">
            {metaPrimary ? <span>{metaPrimary}</span> : null}
            {metaSecondary ? <span>{metaSecondary}</span> : null}
          </p>
        )}
      </div>

      {children ? (
        <>
          <div className="divider page-divider"></div>
          <div className="page-header-body">{children}</div>
        </>
      ) : null}
    </section>
  );
}
