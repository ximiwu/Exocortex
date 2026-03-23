import type { AppStoreSliceCreator, ShellUiSlice } from "../appStore.types";
import { getInitialTheme } from "../utils";

export const createShellUiSlice: AppStoreSliceCreator<ShellUiSlice> = (set) => ({
  theme: getInitialTheme(),
  importDialogOpen: false,
  activeTaskPanel: false,
  sidebarCollapsed: false,
  setTheme: (theme) => set({ theme }),
  toggleTheme: () =>
    set((state) => ({
      theme: state.theme === "dark" ? "light" : "dark",
    })),
  setImportDialogOpen: (open) => set({ importDialogOpen: open }),
  setActiveTaskPanel: (active) => set({ activeTaskPanel: active }),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
});
