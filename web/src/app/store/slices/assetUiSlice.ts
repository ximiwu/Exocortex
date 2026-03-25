import type { AppStoreSliceCreator, AssetUiSlice } from "../appStore.types";
import { basename } from "../utils";
import {
  DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
  DEFAULT_SIDEBAR_WIDTH_RATIO,
  normalizePaneRatio,
} from "../../shell/paneLayout";

export const createAssetUiSlice: AppStoreSliceCreator<AssetUiSlice> = (set) => ({
  selectedAssetName: null,
  sidebarWidthRatio: DEFAULT_SIDEBAR_WIDTH_RATIO,
  rightRailWidthRatio: DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
  setSelectedAssetName: (assetName) => {
    set((state) => {
      if (assetName === null) {
        return {
          selectedAssetName: null,
          currentMarkdownPath: null,
          compressSelection: null,
          sidebarWidthRatio: DEFAULT_SIDEBAR_WIDTH_RATIO,
          rightRailWidthRatio: DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
        };
      }

      const firstTabForAsset = state.openTabs.find((tab) => tab.assetName === assetName) ?? null;
      const currentTabStillVisible = state.openTabs.some(
        (tab) => tab.assetName === assetName && tab.path === state.currentMarkdownPath,
      );

      return {
        selectedAssetName: assetName,
        currentMarkdownPath: currentTabStillVisible ? state.currentMarkdownPath : firstTabForAsset?.path ?? null,
        compressSelection: state.selectedAssetName === assetName ? state.compressSelection : null,
        sidebarWidthRatio:
          state.selectedAssetName === assetName
            ? state.sidebarWidthRatio
            : DEFAULT_SIDEBAR_WIDTH_RATIO,
        rightRailWidthRatio:
          state.selectedAssetName === assetName
            ? state.rightRailWidthRatio
            : DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
      };
    });
  },
  setSidebarWidthRatio: (ratio) =>
    set({
      sidebarWidthRatio: normalizePaneRatio(ratio, DEFAULT_SIDEBAR_WIDTH_RATIO),
    }),
  setRightRailWidthRatio: (ratio) =>
    set({
      rightRailWidthRatio: normalizePaneRatio(ratio, DEFAULT_RIGHT_RAIL_WIDTH_RATIO),
    }),
  hydrateAssetUiState: (assetName, state) => {
    set((current) => {
      const rawUiState = state.uiState as typeof state.uiState & {
        sidebarWidthRatio?: unknown;
        rightRailWidthRatio?: unknown;
      };
      const nextPage = Math.max(1, Math.floor(state.uiState.currentPage || 1));
      const nextZoom = state.uiState.zoom > 0 ? state.uiState.zoom : 1;
      const nextPath = state.uiState.currentMarkdownPath;
      const persistedOpenPaths = Array.isArray(state.uiState.openMarkdownPaths)
        ? state.uiState.openMarkdownPaths.filter((path): path is string => Boolean(path))
        : [];
      const persistedMarkdownScrollFractions = state.uiState.markdownScrollFractions ?? {};
      const localMarkdownScrollFractions = current.markdownScrollFractionsByAsset[assetName] ?? {};
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
          [assetName]: {
            ...persistedMarkdownScrollFractions,
            ...localMarkdownScrollFractions,
          },
        },
        currentMarkdownPath: hasActivePathForAsset ? current.currentMarkdownPath : fallbackPath,
        sidebarWidthRatio: normalizePaneRatio(
          typeof rawUiState.sidebarWidthRatio === "number" ? rawUiState.sidebarWidthRatio : null,
          DEFAULT_SIDEBAR_WIDTH_RATIO,
        ),
        rightRailWidthRatio: normalizePaneRatio(
          typeof rawUiState.rightRailWidthRatio === "number" ? rawUiState.rightRailWidthRatio : null,
          DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
        ),
      };
    });
  },
});
