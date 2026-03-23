import type {
  AppStoreSliceCreator,
  WorkspaceTabsSlice,
} from "../appStore.types";

export const createWorkspaceTabsSlice: AppStoreSliceCreator<WorkspaceTabsSlice> = (set) => ({
  currentMarkdownPath: null,
  sidebarCollapsedNodeIdsByAsset: {},
  sidebarRevealTarget: null,
  openTabs: [],
  markdownScrollFractionsByAsset: {},
  setCurrentMarkdownPath: (path) => set({ currentMarkdownPath: path }),
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

      const finalActiveTab = tabs.find((tab) => tab.path === activePath) ?? tabs.at(-1) ?? null;

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

      if (
        !state.currentMarkdownPath ||
        !pathSet.has(state.currentMarkdownPath) ||
        state.selectedAssetName !== assetName
      ) {
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
});
