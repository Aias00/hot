import { Outlet } from "react-router-dom";

import Sidebar from "./Sidebar";

export default function AppLayout({ themePreference, onThemeChange }) {
  return (
    <>
      <div className="page-noise" aria-hidden="true"></div>
      <div className="page-aura" aria-hidden="true"></div>

      <div className="app-shell">
        <Sidebar
          themePreference={themePreference}
          onThemeChange={onThemeChange}
        />

        <main className="app-main" id="top">
          <Outlet />
        </main>
      </div>
    </>
  );
}
