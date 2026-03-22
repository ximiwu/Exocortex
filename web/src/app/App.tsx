import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";

import { useExocortexApi } from "./api/ExocortexApiContext";
import { queryKeys } from "./api/exocortexApi";
import { WorkbenchShell } from "./shell/WorkbenchShell";
import { useAppStore } from "./store/appStore";
import type { AssetSummary, MarkdownTreeNode } from "./types";

const EMPTY_ASSETS: AssetSummary[] = [];
const EMPTY_TREE: MarkdownTreeNode[] = [];
const EMPTY_PATHS: string[] = [];
const THEME_STORAGE_KEY = "exocortex-web-theme";

export default function App() {
  const api = useExocortexApi();
  const theme = useAppStore((state) => state.theme);
  const selectedAssetName = useAppStore((state) => state.selectedAssetName);
  const setSelectedAssetName = useAppStore((state) => state.setSelectedAssetName);
  const hydrateAssetUiState = useAppStore((state) => state.hydrateAssetUiState);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const openTabs = useAppStore((state) => state.openTabs);
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed);
  const sidebarCollapsedNodeIdsByAsset = useAppStore((state) => state.sidebarCollapsedNodeIdsByAsset);
  const markdownScrollFractionsByAsset = useAppStore((state) => state.markdownScrollFractionsByAsset);
  const hydrationSignaturesRef = useRef<Record<string, string>>({});
  const skipNextPersistSignatureRef = useRef<Record<string, string>>({});
  const openMarkdownPaths = selectedAssetName
    ? openTabs.filter((tab) => tab.assetName === selectedAssetName).map((tab) => tab.path)
    : EMPTY_PATHS;

  const assetsQuery = useQuery({
    queryKey: queryKeys.assets,
    queryFn: () => api.assets.list(),
  });

  const assetStateQuery = useQuery({
    queryKey: queryKeys.assetState(selectedAssetName),
    queryFn: () => api.assets.getState(selectedAssetName!),
    enabled: Boolean(selectedAssetName),
  });

  const markdownTreeQuery = useQuery({
    queryKey: queryKeys.markdownTree(selectedAssetName),
    queryFn: () => api.markdown.getTree(selectedAssetName!),
    enabled: Boolean(selectedAssetName),
  });

  const assets = assetsQuery.data ?? EMPTY_ASSETS;
  const assetState = assetStateQuery.data ?? null;
  const markdownTree = markdownTreeQuery.data ?? EMPTY_TREE;
  const dataSource = api.mode;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (selectedAssetName && assets.some((asset) => asset.name === selectedAssetName)) {
      return;
    }

    if (!assets.length || selectedAssetName) {
      setSelectedAssetName(null);
    }
  }, [assets, selectedAssetName, setSelectedAssetName]);

  useEffect(() => {
    if (!selectedAssetName || !assetState) {
      return;
    }

    const signature = JSON.stringify(assetState.uiState);
    if (hydrationSignaturesRef.current[selectedAssetName] === signature) {
      return;
    }

    skipNextPersistSignatureRef.current[selectedAssetName] = signature;
    hydrateAssetUiState(selectedAssetName, assetState);
    hydrationSignaturesRef.current[selectedAssetName] = signature;
  }, [assetState, hydrateAssetUiState, selectedAssetName]);

  useEffect(() => {
    if (dataSource !== "live" || !selectedAssetName || !assetState) {
      return;
    }

    const localCurrentMarkdownPath =
      currentMarkdownPath && openMarkdownPaths.includes(currentMarkdownPath)
        ? currentMarkdownPath
        : null;
    const localOpenMarkdownPaths = dedupePaths([
      ...openMarkdownPaths,
      ...(localCurrentMarkdownPath ? [localCurrentMarkdownPath] : []),
    ]);
    const remoteOpenMarkdownPaths = dedupePaths([
      ...(assetState.uiState.openMarkdownPaths ?? []),
      ...(assetState.uiState.currentMarkdownPath ? [assetState.uiState.currentMarkdownPath] : []),
    ]);
    const localSidebarCollapsedNodeIds = selectedAssetName
      ? sidebarCollapsedNodeIdsByAsset[selectedAssetName] ?? EMPTY_PATHS
      : EMPTY_PATHS;
    const remoteSidebarCollapsedNodeIds = assetState.uiState.sidebarCollapsedNodeIds ?? EMPTY_PATHS;
    const localMarkdownScrollFractions = selectedAssetName
      ? markdownScrollFractionsByAsset[selectedAssetName] ?? {}
      : {};
    const remoteMarkdownScrollFractions = assetState.uiState.markdownScrollFractions ?? {};
    const signature = JSON.stringify(assetState.uiState);

    if (skipNextPersistSignatureRef.current[selectedAssetName] === signature) {
      delete skipNextPersistSignatureRef.current[selectedAssetName];
      return;
    }

    if (
      assetState.uiState.currentMarkdownPath === localCurrentMarkdownPath &&
      samePaths(remoteOpenMarkdownPaths, localOpenMarkdownPaths) &&
      Boolean(assetState.uiState.sidebarCollapsed) === sidebarCollapsed &&
      samePaths(remoteSidebarCollapsedNodeIds, localSidebarCollapsedNodeIds) &&
      sameNumberMap(remoteMarkdownScrollFractions, localMarkdownScrollFractions)
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      void api.assets.updateUiState(selectedAssetName, {
        currentMarkdownPath: localCurrentMarkdownPath,
        openMarkdownPaths: localOpenMarkdownPaths,
        sidebarCollapsed,
        sidebarCollapsedNodeIds: localSidebarCollapsedNodeIds,
        markdownScrollFractions: localMarkdownScrollFractions,
      }).catch((error) => {
        console.warn("Failed to persist asset UI state", error);
      });
    }, 250);

    return () => {
      window.clearTimeout(timer);
    };
  }, [
    assetState,
    currentMarkdownPath,
    dataSource,
    markdownScrollFractionsByAsset,
    openMarkdownPaths,
    api,
    selectedAssetName,
    sidebarCollapsed,
    sidebarCollapsedNodeIdsByAsset,
  ]);

  return (
    <WorkbenchShell
      assets={assets}
      markdownTree={markdownTree}
      dataSource={dataSource}
      assetsLoading={assetsQuery.isLoading}
      assetsError={assetsQuery.error instanceof Error ? assetsQuery.error.message : null}
      treeLoading={markdownTreeQuery.isLoading}
      treeError={markdownTreeQuery.error instanceof Error ? markdownTreeQuery.error.message : null}
    />
  );
}

function dedupePaths(paths: string[]): string[] {
  return Array.from(new Set(paths.filter(Boolean)));
}

function samePaths(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((value, index) => value === right[index]);
}

function sameNumberMap(left: Record<string, number>, right: Record<string, number>): boolean {
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) {
    return false;
  }

  return leftKeys.every((key) => left[key] === right[key]);
}
