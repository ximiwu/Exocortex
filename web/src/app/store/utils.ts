import type { ThemeMode } from "../types";

export const THEME_STORAGE_KEY = "exocortex-web-theme";

export function basename(path: string): string {
  const cleaned = path.replaceAll("\\", "/");
  return cleaned.split("/").filter(Boolean).at(-1) ?? path;
}

export function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "light";
  }

  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return storedTheme === "dark" ? "dark" : "light";
}
