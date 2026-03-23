import { useEffect, useRef } from "react";

import type { ExocortexApi } from "../api/exocortexApi";
import type { AssetState, AssetSummary } from "../types";
import { useAppStore } from "../store/appStore";
import { dedupePaths, sameNumberMap, samePaths } from "../store/selectors";
import {
  DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
  DEFAULT_SIDEBAR_WIDTH_RATIO,
  normalizePaneRatio,
} from "../shell/paneLayout";

const EMPTY_PATHS: string[] = [];
const EMPTY_ASSETS: AssetSummary[] = [];

interface UseAssetUiStateSyncOptions {
  api: Pick<ExocortexApi, "mode" | "assets">;
  assets?: AssetSummary[] | null;
  assetState?: AssetState | null;
  persistDelayMs?: number;
}

export function useAssetUiStateSync({
  api,
  assets,
  assetState,
  persistDelayMs = 250,
}: UseAssetUiStateSyncOptions): void {
  const resolvedAssets = assets ?? EMPTY_ASSETS;
  const resolvedAssetState = assetState ?? null;
  const selectedAssetName = useAppStore((state) => state.selectedAssetName);
  const setSelectedAssetName = useAppStore((state) => state.setSelectedAssetName);
  const hydrateAssetUiState = useAppStore((state) => state.hydrateAssetUiState);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const openTabs = useAppStore((state) => state.openTabs);
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed);
  const sidebarWidthRatio = useAppStore((state) => state.sidebarWidthRatio);
  const rightRailWidthRatio = useAppStore((state) => state.rightRailWidthRatio);
  const sidebarCollapsedNodeIdsByAsset = useAppStore((state) => state.sidebarCollapsedNodeIdsByAsset);
  const markdownScrollFractionsByAsset = useAppStore((state) => state.markdownScrollFractionsByAsset);
  const hydrationSignaturesRef = useRef<Record<string, string>>({});
  const skipNextPersistSignatureRef = useRef<Record<string, string>>({});

  const openMarkdownPaths = selectedAssetName
    ? openTabs.filter((tab) => tab.assetName === selectedAssetName).map((tab) => tab.path)
    : EMPTY_PATHS;

  useEffect(() => {
    if (selectedAssetName && resolvedAssets.some((asset) => asset.name === selectedAssetName)) {
      return;
    }

    if (!resolvedAssets.length || selectedAssetName) {
      setSelectedAssetName(null);
    }
  }, [resolvedAssets, selectedAssetName, setSelectedAssetName]);

  useEffect(() => {
    if (!selectedAssetName || !resolvedAssetState) {
      return;
    }

    const signature = JSON.stringify(resolvedAssetState.uiState);
    if (hydrationSignaturesRef.current[selectedAssetName] === signature) {
      return;
    }

    skipNextPersistSignatureRef.current[selectedAssetName] = signature;
    hydrateAssetUiState(selectedAssetName, resolvedAssetState);
    hydrationSignaturesRef.current[selectedAssetName] = signature;
  }, [resolvedAssetState, hydrateAssetUiState, selectedAssetName]);

  useEffect(() => {
    if (api.mode !== "live" || !selectedAssetName || !resolvedAssetState) {
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
      ...(resolvedAssetState.uiState.openMarkdownPaths ?? []),
      ...(resolvedAssetState.uiState.currentMarkdownPath ? [resolvedAssetState.uiState.currentMarkdownPath] : []),
    ]);
    const localSidebarCollapsedNodeIds = selectedAssetName
      ? sidebarCollapsedNodeIdsByAsset[selectedAssetName] ?? EMPTY_PATHS
      : EMPTY_PATHS;
    const remoteSidebarCollapsedNodeIds = resolvedAssetState.uiState.sidebarCollapsedNodeIds ?? EMPTY_PATHS;
    const localMarkdownScrollFractions = selectedAssetName
      ? markdownScrollFractionsByAsset[selectedAssetName] ?? {}
      : {};
    const remoteMarkdownScrollFractions = resolvedAssetState.uiState.markdownScrollFractions ?? {};
    const rawUiState = resolvedAssetState.uiState as typeof resolvedAssetState.uiState & {
      sidebarWidthRatio?: unknown;
      rightRailWidthRatio?: unknown;
    };
    const remoteSidebarWidthRatio = normalizePaneRatio(
      typeof rawUiState.sidebarWidthRatio === "number" ? rawUiState.sidebarWidthRatio : null,
      DEFAULT_SIDEBAR_WIDTH_RATIO,
    );
    const remoteRightRailWidthRatio = normalizePaneRatio(
      typeof rawUiState.rightRailWidthRatio === "number" ? rawUiState.rightRailWidthRatio : null,
      DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
    );
    const signature = JSON.stringify(resolvedAssetState.uiState);

    if (skipNextPersistSignatureRef.current[selectedAssetName] === signature) {
      delete skipNextPersistSignatureRef.current[selectedAssetName];
      return;
    }

    if (
      resolvedAssetState.uiState.currentMarkdownPath === localCurrentMarkdownPath &&
      samePaths(remoteOpenMarkdownPaths, localOpenMarkdownPaths) &&
      Boolean(resolvedAssetState.uiState.sidebarCollapsed) === sidebarCollapsed &&
      samePaths(remoteSidebarCollapsedNodeIds, localSidebarCollapsedNodeIds) &&
      sameNumberMap(remoteMarkdownScrollFractions, localMarkdownScrollFractions) &&
      remoteSidebarWidthRatio === sidebarWidthRatio &&
      remoteRightRailWidthRatio === rightRailWidthRatio
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      const nextUiState = {
        currentMarkdownPath: localCurrentMarkdownPath,
        openMarkdownPaths: localOpenMarkdownPaths,
        sidebarCollapsed,
        sidebarCollapsedNodeIds: localSidebarCollapsedNodeIds,
        markdownScrollFractions: localMarkdownScrollFractions,
        sidebarWidthRatio,
        rightRailWidthRatio,
      } as Partial<AssetState["uiState"]> & {
        sidebarWidthRatio: number;
        rightRailWidthRatio: number;
      };

      void api.assets
        .updateUiState(selectedAssetName, nextUiState)
        .catch((error) => {
          console.warn("Failed to persist asset UI state", error);
        });
    }, persistDelayMs);

    return () => {
      window.clearTimeout(timer);
    };
  }, [
    api,
    resolvedAssetState,
    currentMarkdownPath,
    markdownScrollFractionsByAsset,
    openMarkdownPaths,
    persistDelayMs,
    rightRailWidthRatio,
    selectedAssetName,
    sidebarCollapsed,
    sidebarCollapsedNodeIdsByAsset,
    sidebarWidthRatio,
  ]);
}
