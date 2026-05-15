import { useEffect, useState } from "react";

import { useAuth } from "../../hooks/useAuth.jsx";

export default function AdminOverview() {
  const { authFetch } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      try {
        const [sourcesRes] = await Promise.all([authFetch("/api/admin/sources")]);
        const sources = await sourcesRes.json();
        setStats({
          sourcesCount: sources.length,
          enabledSources: sources.filter((s) => s.enabled).length,
        });
      } catch (error) {
        console.error("Failed to load stats:", error);
      } finally {
        setLoading(false);
      }
    }
    loadStats();
  }, [authFetch]);

  if (loading) {
    return <div className="admin-overview">加载中...</div>;
  }

  return (
    <div className="admin-overview">
      <h1 className="admin-overview__title">概览</h1>
      <div className="admin-overview__stats">
        <div className="admin-overview__stat">
          <div className="admin-overview__stat-value">{stats?.sourcesCount || 0}</div>
          <div className="admin-overview__stat-label">采集源总数</div>
        </div>
        <div className="admin-overview__stat">
          <div className="admin-overview__stat-value">{stats?.enabledSources || 0}</div>
          <div className="admin-overview__stat-label">已启用</div>
        </div>
      </div>
    </div>
  );
}
