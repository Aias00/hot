import { useEffect, useState } from "react";

// Fallback navigation items if API fails
const DEFAULT_NAV_ITEMS = [
  { icon: "◫", label: "导航中心", to: "/nav-hub" },
  { icon: "☰", label: "全部 AI 动态", to: "/all" },
  { icon: "◉", label: "关于", to: "/about" },
];

export function useNavigation() {
  const [navItems, setNavItems] = useState(DEFAULT_NAV_ITEMS);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadNavigation() {
      try {
        const response = await fetch("/api/navigation");
        if (response.ok) {
          const data = await response.json();
          // Filter enabled items and map to expected format
          const items = data
            .filter((item) => item.enabled)
            .map((item) => ({
              icon: item.icon,
              label: item.label,
              to: item.to,
            }));
          if (items.length > 0) {
            setNavItems(items);
          }
        }
      } catch (error) {
        console.error("Failed to load navigation:", error);
        // Keep default items on error
      } finally {
        setLoading(false);
      }
    }
    loadNavigation();
  }, []);

  return { navItems, loading };
}
