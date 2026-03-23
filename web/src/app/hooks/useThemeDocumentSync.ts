import { useEffect, useRef } from "react";

import type { ExocortexApi } from "../api/exocortexApi";
import type { ThemeMode } from "../types";
import { useAppStore } from "../store/appStore";
import { selectTheme } from "../store/selectors";
import { THEME_STORAGE_KEY } from "../store/utils";

export function useThemeDocumentSync(theme: ThemeMode): void {
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);
}

export function useThemeDocumentSyncFromStore(): ThemeMode {
  const theme = useAppStore(selectTheme);
  useThemeDocumentSync(theme);
  return theme;
}

export function useThemeConfigSync(systemApi: ExocortexApi["system"]): void {
  const theme = useAppStore(selectTheme);
  const setTheme = useAppStore((state) => state.setTheme);
  const hydratedRef = useRef(false);
  const persistedThemeRef = useRef<ThemeMode | null>(null);

  useEffect(() => {
    let cancelled = false;

    void systemApi
      .getConfig()
      .then((config) => {
        if (cancelled) {
          return;
        }

        persistedThemeRef.current = config.themeMode;
        hydratedRef.current = true;
        setTheme(config.themeMode);
      })
      .catch((error) => {
        hydratedRef.current = true;
        console.warn("Failed to load theme preference", error);
      });

    return () => {
      cancelled = true;
    };
  }, [setTheme, systemApi]);

  useEffect(() => {
    if (!hydratedRef.current || persistedThemeRef.current === theme) {
      return;
    }

    let cancelled = false;

    void (async () => {
      try {
        const persisted = await systemApi.updateConfig({ themeMode: theme });
        if (cancelled) {
          return;
        }

        persistedThemeRef.current = persisted.themeMode;
      } catch (error) {
        console.warn("Failed to save theme preference", error);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [systemApi, theme]);
}
