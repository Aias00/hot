import { mediaThemes } from "../data/visualThemes";
import { getMediaThemeIndex } from "../lib/feed";

export default function MediaShell({ item }) {
  const background =
    `${mediaThemes[getMediaThemeIndex(item.source, item.time, mediaThemes.length)]}, ` +
    "linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03))";

  return (
    <div className="media-shell" style={{ backgroundImage: background }}>
      <div className="media-glow" aria-hidden="true"></div>
      <div className="media-content">
        <span className="media-kicker">媒体预览</span>
        <strong className="media-label">{item.title || item.source}</strong>
        <span className="media-caption">
          {item.tags?.slice(0, 2).join(" · ") || "精选媒体预览"}
        </span>
      </div>
      <span className="media-action" aria-hidden="true">
        ↗
      </span>
    </div>
  );
}
