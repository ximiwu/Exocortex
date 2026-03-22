import { create } from "zustand";

import { AppMode, AssetState, MarkdownTab, Rect, ThemeMode } from "../types";

const THEME_STORAGE_KEY = "exocortex-web-theme";

type MarkdownOpenSource = "sidebar" | "external";

interface SidebarRevealTarget {
  assetName: string;
  path: string;
  nonce: number;
}

interface MarkdownContextMenuRequest {
  x: number;
  y: number;
  nonce: number;
}

interface GroupDiveRequest {
  assetName: string;
  groupIdx: number;
  nonce: number;
}

interface AssetDeleteRequest {
  assetName: string;
  nonce: number;
}

interface AppStoreState {
  theme: ThemeMode;
  selectedAssetName: string | null;
  importDialogOpen: boolean;
  currentMarkdownPath: string | null;
  currentPage: number;
  zoom: number;
  selectedBlockIds: number[];
  hoveredBlockId: number | null;
  hoveredGroupIdx: number | null;
  appMode: AppMode;
  activeTaskPanel: boolean;
  sidebarCollapsed: boolean;
  sidebarCollapsedNodeIdsByAsset: Record<string, string[]>;
  sidebarRevealTarget: SidebarRevealTarget | null;
  compressSelection: Rect | null;
  openTabs: MarkdownTab[];
  markdownScrollFractionsByAsset: Record<string, Record<string, number>>;
  markdownContextMenuRequest: MarkdownContextMenuRequest | null;
  groupDiveRequest: GroupDiveRequest | null;
  assetDeleteRequest: AssetDeleteRequest | null;
  setSelectedAssetName: (assetName: string | null) => void;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  setImportDialogOpen: (open: boolean) => void;
  setCurrentMarkdownPath: (path: string | null) => void;
  setCurrentPage: (page: number) => void;
  setZoom: (zoom: number) => void;
  setActiveTaskPanel: (active: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebarNode: (assetName: string, nodeId: string) => void;
  setAppMode: (mode: AppMode) => void;
  setCompressSelection: (selection: Rect | null) => void;
  openMarkdownTab: (tab: MarkdownTab, options?: { source?: MarkdownOpenSource }) => void;
  openMarkdownTabs: (tabs: MarkdownTab[], activePath?: string | null) => void;
  closeMarkdownTab: (assetName: string, path: string) => void;
  closeMarkdownTabs: (assetName: string, paths: string[]) => void;
  clearSidebarRevealTarget: () => void;
  rememberMarkdownScroll: (assetName: string, path: string, fraction: number) => void;
  requestMarkdownContextMenu: (x: number, y: number) => void;
  consumeMarkdownContextMenuRequest: () => void;
  requestGroupDive: (assetName: string, groupIdx: number) => void;
  consumeGroupDiveRequest: () => void;
  requestAssetDelete: (assetName: string) => void;
  consumeAssetDeleteRequest: () => void;
  hydrateAssetUiState: (assetName: string, state: AssetState) => void;
}

function basename(path: string) {
  const cleaned = path.replaceAll("\\", "/");
  return cleaned.split("/").filter(Boolean).at(-1) ?? path;
}

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "light";
  }

  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return storedTheme === "dark" ? "dark" : "light";
}

export const useAppStore = create<AppStoreState>((set) => ({
  theme: getInitialTheme(),
  selectedAssetName: null,
  importDialogOpen: false,
  currentMarkdownPath: null,
  currentPage: 1,
  zoom: 1,
  selectedBlockIds: [],
  hoveredBlockId: null,
  hoveredGroupIdx: null,
  appMode: "normal",
  activeTaskPanel: false,
  sidebarCollapsed: false,
  sidebarCollapsedNodeIdsByAsset: {},
  sidebarRevealTarget: null,
  compressSelection: null,
  openTabs: [],
  markdownScrollFractionsByAsset: {},
  markdownContextMenuRequest: null,
  groupDiveRequest: null,
  assetDeleteRequest: null,
  setTheme: (theme) => set({ theme }),
  toggleTheme: () =>
    set((state) => ({
      theme: state.theme === "dark" ? "light" : "dark",
    })),
  setSelectedAssetName: (assetName) => {
    set((state) => {
      if (assetName === null) {
        return {
          selectedAssetName: null,
          currentMarkdownPath: null,
          compressSelection: null,
        };
      }

      const firstTabForAsset = state.openTabs.find((tab) => tab.assetName === assetName) ?? null;
      const currentTabStillVisible = state.openTabs.some(
        (tab) => tab.assetName === assetName && tab.path === state.currentMarkdownPath,
      );

      return {
        selectedAssetName: assetName,
        currentMarkdownPath: currentTabStillVisible ? state.currentMarkdownPath : firstTabForAsset?.path ?? null,
        compressSelection:
          state.selectedAssetName === assetName ? state.compressSelection : null,
      };
    });
  },
  setImportDialogOpen: (open) => set({ importDialogOpen: open }),
  setCurrentMarkdownPath: (path) => set({ currentMarkdownPath: path }),
  setCurrentPage: (page) => set({ currentPage: Math.max(1, Math.floor(page || 1)) }),
  setZoom: (zoom) => set({ zoom }),
  setActiveTaskPanel: (active) => set({ activeTaskPanel: active }),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebarNode: (assetName, nodeId) => {
    set((state) => {
      if (!assetName || !nodeId) {
        return state;
      }

      const current = new Set(state.sidebarCollapsedNodeIdsByAsset[assetName] ?? []);
      if (current.has(nodeId)) {
        current.delete(nodeId);
      } else {
        current.add(nodeId);
      }

      return {
        sidebarCollapsedNodeIdsByAsset: {
          ...state.sidebarCollapsedNodeIdsByAsset,
          [assetName]: Array.from(current),
        },
      };
    });
  },
  setAppMode: (mode) => set({ appMode: mode }),
  setCompressSelection: (selection) => set({ compressSelection: selection }),
  openMarkdownTab: (tab, options) => {
    set((state) => {
      const existingIndex = state.openTabs.findIndex(
        (candidate) => candidate.assetName === tab.assetName && candidate.path === tab.path,
      );

      const openTabs = [...state.openTabs];
      if (existingIndex >= 0) {
        openTabs[existingIndex] = {
          ...openTabs[existingIndex],
          ...tab,
        };
      } else {
        openTabs.push(tab);
      }

      return {
        selectedAssetName: tab.assetName,
        currentMarkdownPath: tab.path,
        openTabs,
        sidebarRevealTarget:
          options?.source === "sidebar"
            ? null
            : {
                assetName: tab.assetName,
                path: tab.path,
                nonce: Date.now(),
              },
      };
    });
  },
  openMarkdownTabs: (tabs, activePath) => {
    set((state) => {
      if (!tabs.length) {
        return state;
      }

      const openTabs = [...state.openTabs];
      for (const tab of tabs) {
        const existingIndex = openTabs.findIndex(
          (candidate) => candidate.assetName === tab.assetName && candidate.path === tab.path,
        );

        if (existingIndex >= 0) {
          openTabs[existingIndex] = {
            ...openTabs[existingIndex],
            ...tab,
          };
        } else {
          openTabs.push(tab);
        }
      }

      const finalActiveTab =
        tabs.find((tab) => tab.path === activePath) ?? tabs.at(-1) ?? null;

      return finalActiveTab
        ? {
            selectedAssetName: finalActiveTab.assetName,
            currentMarkdownPath: finalActiveTab.path,
            openTabs,
          }
        : { openTabs };
    });
  },
  closeMarkdownTab: (assetName, path) => {
    set((state) => {
      const tabsForAsset = state.openTabs.filter((tab) => tab.assetName === assetName);
      const closingIndex = tabsForAsset.findIndex((tab) => tab.path === path);
      const openTabs = state.openTabs.filter(
        (tab) => !(tab.assetName === assetName && tab.path === path),
      );

      if (state.currentMarkdownPath !== path || state.selectedAssetName !== assetName) {
        return { openTabs };
      }

      const remainingTabs = tabsForAsset.filter((tab) => tab.path !== path);
      const nextIndex = closingIndex <= 0 ? 0 : closingIndex - 1;
      const nextTab = remainingTabs[nextIndex] ?? null;

      return {
        openTabs,
        currentMarkdownPath: nextTab?.path ?? null,
      };
    });
  },
  closeMarkdownTabs: (assetName, paths) => {
    set((state) => {
      const pathSet = new Set(paths.filter(Boolean));
      if (!assetName || pathSet.size === 0) {
        return state;
      }

      const tabsForAsset = state.openTabs.filter((tab) => tab.assetName === assetName);
      const remainingTabsForAsset = tabsForAsset.filter((tab) => !pathSet.has(tab.path));
      const openTabs = state.openTabs.filter(
        (tab) => tab.assetName !== assetName || !pathSet.has(tab.path),
      );

      if (!state.currentMarkdownPath || !pathSet.has(state.currentMarkdownPath) || state.selectedAssetName !== assetName) {
        return { openTabs };
      }

      const nextTab = remainingTabsForAsset.at(-1) ?? null;
      return {
        openTabs,
        currentMarkdownPath: nextTab?.path ?? null,
      };
    });
  },
  clearSidebarRevealTarget: () => set({ sidebarRevealTarget: null }),
  rememberMarkdownScroll: (assetName, path, fraction) => {
    set((state) => ({
      markdownScrollFractionsByAsset: {
        ...state.markdownScrollFractionsByAsset,
        [assetName]: {
          ...(state.markdownScrollFractionsByAsset[assetName] ?? {}),
          [path]: Math.min(1, Math.max(0, fraction)),
        },
      },
    }));
  },
  requestMarkdownContextMenu: (x, y) =>
    set({
      markdownContextMenuRequest: {
        x,
        y,
        nonce: Date.now(),
      },
    }),
  consumeMarkdownContextMenuRequest: () => set({ markdownContextMenuRequest: null }),
  requestGroupDive: (assetName, groupIdx) =>
    set({
      groupDiveRequest: {
        assetName,
        groupIdx,
        nonce: Date.now(),
      },
    }),
  consumeGroupDiveRequest: () => set({ groupDiveRequest: null }),
  requestAssetDelete: (assetName) =>
    set({
      assetDeleteRequest: {
        assetName,
        nonce: Date.now(),
      },
    }),
  consumeAssetDeleteRequest: () => set({ assetDeleteRequest: null }),
  hydrateAssetUiState: (assetName, state) => {
    set((current) => {
      const nextPage = Math.max(1, Math.floor(state.uiState.currentPage || 1));
      const nextZoom = state.uiState.zoom > 0 ? state.uiState.zoom : 1;
      const nextPath = state.uiState.currentMarkdownPath;
      const persistedOpenPaths = Array.isArray(state.uiState.openMarkdownPaths)
        ? state.uiState.openMarkdownPaths.filter((path): path is string => Boolean(path))
        : [];
      const nextOpenPaths = Array.from(
        new Set([...(nextPath ? [nextPath] : []), ...persistedOpenPaths]),
      );
      const tabsForAsset = current.openTabs.filter((tab) => tab.assetName === assetName);
      let openTabs = current.openTabs;

      for (const path of nextOpenPaths) {
        if (tabsForAsset.some((tab) => tab.path === path)) {
          continue;
        }

        openTabs = [
          ...openTabs,
          {
            assetName,
            path,
            title: basename(path),
            kind: "markdown",
          },
        ];
      }

      const hasActivePathForAsset = openTabs.some(
        (tab) => tab.assetName === assetName && tab.path === current.currentMarkdownPath,
      );
      const fallbackPath = nextPath ?? nextOpenPaths[0] ?? null;

      return {
        openTabs,
        selectedAssetName: assetName,
        currentPage: nextPage,
        zoom: nextZoom,
        sidebarCollapsed: Boolean(state.uiState.sidebarCollapsed),
        sidebarCollapsedNodeIdsByAsset: {
          ...current.sidebarCollapsedNodeIdsByAsset,
          [assetName]: Array.isArray(state.uiState.sidebarCollapsedNodeIds)
            ? state.uiState.sidebarCollapsedNodeIds.filter((nodeId): nodeId is string => Boolean(nodeId))
            : [],
        },
        markdownScrollFractionsByAsset: {
          ...current.markdownScrollFractionsByAsset,
          [assetName]: state.uiState.markdownScrollFractions ?? {},
        },
        currentMarkdownPath: hasActivePathForAsset ? current.currentMarkdownPath : fallbackPath,
      };
    });
  },
}));
