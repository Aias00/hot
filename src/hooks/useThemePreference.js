import { useEffect, useState } from "react";

import { resolveTheme, THEME_STORAGE_KEY } from "../lib/theme";

function normalizeThemePreference(preference) {
  if (preference === "light" || preference === "dark") {
    return preference;
  }

  return resolveTheme("system");
}

export function useThemePreference() {
  const [themePreference, setThemePreference] = useState(
    () => normalizeThemePreference(localStorage.getItem(THEME_STORAGE_KEY)),
  );

  useEffect(() => {
    document.documentElement.dataset.theme = themePreference;
    localStorage.setItem(THEME_STORAGE_KEY, themePreference);
  }, [themePreference]);

  return { themePreference, setThemePreference };
}
