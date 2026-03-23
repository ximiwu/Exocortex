import type { AssetSummary, MarkdownTreeNode } from "../types";
import type { AppStoreState } from "./appStore.types";

const EMPTY_ASSETS: AssetSummary[] = [];
const EMPTY_TREE: MarkdownTreeNode[] = [];
const EMPTY_PATHS: string[] = [];

export interface AppShellDataSnapshot {
  theme: AppStoreState["theme"];
  selectedAssetName: string | null;
  currentMarkdownPath: string | null;
  openTabs: AppStoreState["openTabs"];
  sidebarCollapsed: boolean;
  sidebarCollapsedNodeIdsByAsset: AppStoreState["sidebarCollapsedNodeIdsByAsset"];
  markdownScrollFractionsByAsset: AppStoreState["markdownScrollFractionsByAsset"];
}

export function selectTheme(state: AppStoreState): AppStoreState["theme"] {
  return state.theme;
}

export function selectSelectedAssetName(state: AppStoreState): string | null {
  return state.selectedAssetName;
}

export function selectAppShellDataSnapshot(state: AppStoreState): AppShellDataSnapshot {
  return {
    theme: state.theme,
    selectedAssetName: state.selectedAssetName,
    currentMarkdownPath: state.currentMarkdownPath,
    openTabs: state.openTabs,
    sidebarCollapsed: state.sidebarCollapsed,
    sidebarCollapsedNodeIdsByAsset: state.sidebarCollapsedNodeIdsByAsset,
    markdownScrollFractionsByAsset: state.markdownScrollFractionsByAsset,
  };
}

export function selectOpenMarkdownPathsForSelectedAsset(state: AppStoreState): string[] {
  return getOpenMarkdownPathsForAsset(state, state.selectedAssetName);
}

export function getOpenMarkdownPathsForAsset(
  state: AppStoreState,
  assetName: string | null,
): string[] {
  if (!assetName) {
    return EMPTY_PATHS;
  }

  return state.openTabs.filter((tab) => tab.assetName === assetName).map((tab) => tab.path);
}

export function fallbackAssets(assets: AssetSummary[] | undefined): AssetSummary[] {
  return assets ?? EMPTY_ASSETS;
}

export function fallbackMarkdownTree(tree: MarkdownTreeNode[] | undefined): MarkdownTreeNode[] {
  return tree ?? EMPTY_TREE;
}

export function dedupePaths(paths: string[]): string[] {
  return Array.from(new Set(paths.filter(Boolean)));
}

export function samePaths(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((value, index) => value === right[index]);
}

export function sameNumberMap(left: Record<string, number>, right: Record<string, number>): boolean {
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) {
    return false;
  }

  return leftKeys.every((key) => left[key] === right[key]);
}
