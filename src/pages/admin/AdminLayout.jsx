import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth.jsx";

export default function AdminLayout() {
  const { isAuthenticated, logout } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" state={{ from: location }} replace />;
  }

  const navItems = [
    { to: "/admin", label: "概览", end: true },
    { to: "/admin/sources", label: "采集源" },
    { to: "/admin/navigation", label: "侧边导航" },
    { to: "/admin/nav-hub", label: "导航中心" },
  ];

  return (
    <div className="admin-layout">
      <header className="admin-layout__header">
        <div className="admin-layout__brand">管理后台</div>
        <nav className="admin-layout__nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `admin-layout__nav-item ${isActive ? "admin-layout__nav-item--active" : ""}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button onClick={logout} className="admin-layout__logout">
          退出
        </button>
      </header>
      <main className="admin-layout__main">
        <Outlet />
      </main>
    </div>
  );
}
