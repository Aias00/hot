import { avatarThemes } from "../data/visualThemes";
import { getAvatarLabel, getAvatarThemeIndex } from "../lib/feed";
import MediaShell from "./MediaShell";

export default function TimelineItem({ item }) {
  const avatarBackground =
    avatarThemes[getAvatarThemeIndex(item.source || "AI", avatarThemes.length)];
  const hasTitle = Boolean(item.title);
  const hasBody = Boolean(item.body);
  const bodyCopy = hasTitle ? item.body : item.body || item.title;

  return (
    <article className="timeline-item">
      <div className="timeline-time">{item.time}</div>
      <div className="timeline-rail">
        <span className="timeline-dot"></span>
      </div>
      <div className="timeline-card">
        <div className="timeline-card-head">
          <div className="timeline-head-left">
            <span className="avatar" aria-hidden="true" style={{ background: avatarBackground }}>
              {getAvatarLabel(item.source || "AI")}
            </span>
            <div>
              <span className="timeline-source">{item.source}</span>
              {item.handle ? <span className="timeline-handle">{item.handle}</span> : null}
            </div>
          </div>
          <div className="timeline-head-right">
            <span className="timeline-selected-badge">{item.badge || "精选"}</span>
            <span className="timeline-score mono">{item.score || "--"}</span>
          </div>
        </div>

        <a className="story-link" href={item.link || "#"} target="_blank" rel="noreferrer">
          {hasTitle ? <h2 className="story-title">{item.title}</h2> : null}
          {hasBody ? <p className="story-body">{bodyCopy}</p> : null}
        </a>

        {item.quoted ? <blockquote className="story-quote">{item.quoted}</blockquote> : null}
        {item.hasMedia ? <MediaShell item={item} /> : null}

        {item.tags?.length ? (
          <div className="timeline-tags">
            {item.tags.map((tag) => (
              <span key={tag} className="tag">
                {tag}
              </span>
            ))}
          </div>
        ) : null}

      </div>
    </article>
  );
}
