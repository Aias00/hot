export const THEME_STORAGE_KEY = "aihot-fork-theme";

export function resolveTheme(preference) {
  if (preference === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  return preference;
}
