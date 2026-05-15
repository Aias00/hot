import { useState } from "react";
import { NavLink } from "react-router-dom";

import { navItems } from "../data/navigation";
import { themeOptions } from "../data/themeOptions";

export default function Sidebar({ themePreference, onThemeChange }) {
  const [wechatImageMissing, setWechatImageMissing] = useState(false);

  return (
    <aside className="sidebar">
      <div className="theme-toggle theme-toggle-top" role="radiogroup" aria-label="主题">
        {themeOptions.map((option) => {
          const active = option.value === themePreference;

          return (
            <button
              key={option.value}
              className={`theme-toggle-opt${active ? " is-active" : ""}`}
              type="button"
              data-theme-option={option.value}
              aria-label={option.label}
              aria-checked={active}
              onClick={() => onThemeChange(option.value)}
            >
              {option.icon}
            </button>
          );
        })}
      </div>

      <nav className="side-nav" aria-label="主导航">
        {navItems.map((item) => (
          <NavLink
            key={item.label}
            className={({ isActive }) =>
              `side-link${isActive ? " side-link-active" : ""}`
            }
            to={item.to}
            end={item.end}
          >
            <span className="side-icon">{item.icon}</span>
            <span className="side-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <section className="sidebar-wechat" aria-label="微信公众号二维码">
        {wechatImageMissing ? (
          <div className="sidebar-wechat-fallback">
            <span className="sidebar-wechat-kicker">公众号</span>
            <strong>二维码</strong>
            <small>/public/wechat-qr.png</small>
          </div>
        ) : (
          <img
            className="sidebar-wechat-image"
            src="/wechat-qr.png"
            alt="微信公众号二维码"
            loading="lazy"
            onError={() => setWechatImageMissing(true)}
          />
        )}
      </section>
    </aside>
  );
}
