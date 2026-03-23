import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import { useAppStore } from "../../app/store/appStore";
import { dedupePaths, getOpenMarkdownPathsForAsset } from "../../app/store/selectors";
import type {
  PdfAssetState,
  PdfRect,
  PdfUiState,
} from "./types";

export function usePdfDocument(assetName: string | null) {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
  const [mutating, setMutating] = useState(false);
  const [mutationError, setMutationError] = useState<Error | null>(null);
  const activeAssetNameRef = useRef<string | null>(assetName);
  const uiStateMutationSequenceRef = useRef(0);
  const pendingUiStateMutationsRef = useRef(0);

  useEffect(() => {
    activeAssetNameRef.current = assetName;
    uiStateMutationSequenceRef.current = 0;
    pendingUiStateMutationsRef.current = 0;
    setMutating(false);
    setMutationError(null);
  }, [assetName]);

  const assetStateQuery = useQuery({
    queryKey: queryKeys.assetState(assetName),
    queryFn: () => api.assets.getState(assetName!),
    enabled: Boolean(assetName),
  });

  const metadataQuery = useQuery({
    queryKey: queryKeys.pdfMetadata(assetName),
    queryFn: () => api.pdf.getMetadata(assetName!),
    enabled: Boolean(assetName),
  });

  const assetState = assetStateQuery.data ?? null;
  const metadata = metadataQuery.data ?? null;
  const pdfFileUrl = assetName ? api.pdf.buildFileUrl(assetName) : null;
  const loading = Boolean(assetName) && (assetStateQuery.isPending || metadataQuery.isPending);
  const queryError = toError(assetStateQuery.error ?? metadataQuery.error);
  const error = mutationError ?? queryError;

  function invalidateAssetQueries(
    currentAssetName: string,
    options: {
      includeMarkdownTree?: boolean;
    } = {},
  ): void {
    const { includeMarkdownTree = false } = options;
    void queryClient.invalidateQueries({ queryKey: queryKeys.assets });
    void queryClient.invalidateQueries({ queryKey: queryKeys.assetState(currentAssetName) });
    if (includeMarkdownTree) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(currentAssetName) });
    }
  }

  function writeAssetStateCache(
    currentAssetName: string,
    nextState: PdfAssetState,
    options: {
      overlayLocalShellUi?: boolean;
    } = {},
  ): void {
    const { overlayLocalShellUi = false } = options;
    const normalizedState = overlayLocalShellUi
      ? mergeLocalShellUiState(currentAssetName, nextState)
      : nextState;
    queryClient.setQueryData<PdfAssetState>(
      queryKeys.assetState(currentAssetName),
      normalizedState,
    );
  }

  async function refresh(): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    setMutationError(null);

    try {
      const [assetResult, metadataResult] = await Promise.all([
        assetStateQuery.refetch(),
        metadataQuery.refetch(),
      ]);
      if (assetResult.error) {
        throw assetResult.error;
      }
      if (metadataResult.error) {
        throw metadataResult.error;
      }
      return assetResult.data ?? null;
    } catch (reason) {
      const nextError = toError(reason);
      setMutationError(nextError);
      throw nextError;
    }
  }

  async function createBlock(pageIndex: number, fractionRect: PdfRect): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    setMutating(true);
    setMutationError(null);

    try {
      const nextAssetState = await api.pdf.createBlock(currentAssetName, {
        pageIndex,
        fractionRect,
      });
      writeAssetStateCache(currentAssetName, nextAssetState, {
        overlayLocalShellUi: true,
      });
      invalidateAssetQueries(currentAssetName);
      return nextAssetState;
    } catch (reason) {
      const nextError = toError(reason);
      setMutationError(nextError);
      throw nextError;
    } finally {
      setMutating(false);
    }
  }

  async function deleteBlock(blockId: number): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    setMutating(true);
    setMutationError(null);

    try {
      const nextAssetState = await api.pdf.deleteBlock(currentAssetName, blockId);
      writeAssetStateCache(currentAssetName, nextAssetState, {
        overlayLocalShellUi: true,
      });
      invalidateAssetQueries(currentAssetName);
      return nextAssetState;
    } catch (reason) {
      const nextError = toError(reason);
      setMutationError(nextError);
      throw nextError;
    } finally {
      setMutating(false);
    }
  }

  async function deleteGroup(groupIdx: number): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    setMutating(true);
    setMutationError(null);

    try {
      const nextAssetState = await api.pdf.deleteGroup(currentAssetName, groupIdx);
      writeAssetStateCache(currentAssetName, nextAssetState, {
        overlayLocalShellUi: true,
      });
      invalidateAssetQueries(currentAssetName, {
        includeMarkdownTree: true,
      });
      return nextAssetState;
    } catch (reason) {
      const nextError = toError(reason);
      setMutationError(nextError);
      throw nextError;
    } finally {
      setMutating(false);
    }
  }

  async function updateSelection(mergeOrder: number[]): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    const previousAssetState = queryClient.getQueryData<PdfAssetState>(
      queryKeys.assetState(currentAssetName),
    );
    if (previousAssetState) {
      writeAssetStateCache(currentAssetName, {
        ...previousAssetState,
        mergeOrder: [...mergeOrder],
      });
    }

    setMutating(true);
    setMutationError(null);

    try {
      const nextAssetState = await api.pdf.updateSelection(currentAssetName, mergeOrder);
      writeAssetStateCache(currentAssetName, nextAssetState, {
        overlayLocalShellUi: true,
      });
      return nextAssetState;
    } catch (reason) {
      if (previousAssetState) {
        writeAssetStateCache(currentAssetName, previousAssetState);
      }
      const nextError = toError(reason);
      setMutationError(nextError);
      void refresh();
      throw nextError;
    } finally {
      setMutating(false);
    }
  }

  async function mergeGroup(
    blockIds: number[],
    options: {
      markdownContent?: string | null;
      groupIdx?: number | null;
    } = {},
  ): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    const selectedBlockIds = Array.from(
      new Set(blockIds.map((blockId) => Number(blockId)).filter(Number.isFinite)),
    );
    if (!selectedBlockIds.length) {
      return assetState;
    }

    setMutating(true);
    setMutationError(null);

    try {
      const nextAssetState = await api.pdf.mergeGroup(currentAssetName, selectedBlockIds, options);
      writeAssetStateCache(currentAssetName, nextAssetState, {
        overlayLocalShellUi: true,
      });
      invalidateAssetQueries(currentAssetName, {
        includeMarkdownTree: true,
      });
      return nextAssetState;
    } catch (reason) {
      const nextError = toError(reason);
      setMutationError(nextError);
      throw nextError;
    } finally {
      setMutating(false);
    }
  }

  async function patchUiState(
    patch: Partial<PdfUiState>,
  ): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    const currentAssetState = queryClient.getQueryData<PdfAssetState>(
      queryKeys.assetState(currentAssetName),
    );
    if (!currentAssetName || !currentAssetState) {
      return null;
    }

    const baseUiState = mergeLocalShellUiState(currentAssetName, currentAssetState).uiState;
    const nextUiState: PdfUiState = {
      ...baseUiState,
      ...patch,
    };
    const optimisticState: PdfAssetState = {
      ...currentAssetState,
      uiState: nextUiState,
    };
    const requestSequence = ++uiStateMutationSequenceRef.current;
    pendingUiStateMutationsRef.current += 1;
    writeAssetStateCache(currentAssetName, optimisticState, {
      overlayLocalShellUi: true,
    });

    if (pendingUiStateMutationsRef.current === 1) {
      setMutating(true);
    }
    setMutationError(null);

    try {
      const persistedAssetState = await api.pdf.updateUiState(currentAssetName, nextUiState);
      const normalizedPersistedAssetState = persistedAssetState
        ? mergeLocalShellUiState(currentAssetName, persistedAssetState)
        : optimisticState;
      if (
        activeAssetNameRef.current !== currentAssetName ||
        requestSequence !== uiStateMutationSequenceRef.current
      ) {
        return normalizedPersistedAssetState;
      }

      if (persistedAssetState) {
        writeAssetStateCache(currentAssetName, normalizedPersistedAssetState);
        return normalizedPersistedAssetState;
      }

      return optimisticState;
    } catch (reason) {
      if (
        activeAssetNameRef.current !== currentAssetName ||
        requestSequence !== uiStateMutationSequenceRef.current
      ) {
        return optimisticState;
      }

      writeAssetStateCache(currentAssetName, currentAssetState, {
        overlayLocalShellUi: true,
      });
      const nextError = toError(reason);
      setMutationError(nextError);
      void refresh();
      throw nextError;
    } finally {
      if (activeAssetNameRef.current === currentAssetName) {
        pendingUiStateMutationsRef.current = Math.max(0, pendingUiStateMutationsRef.current - 1);
        if (!pendingUiStateMutationsRef.current) {
          setMutating(false);
        }
      }
    }
  }

  return {
    assetState,
    metadata,
    pdfFileUrl,
    loading,
    mutating,
    error,
    refresh,
    createBlock,
    deleteBlock,
    deleteGroup,
    mergeGroup,
    updateSelection,
    patchUiState,
  };
}

function toError(reason: unknown): Error | null {
  if (!reason) {
    return null;
  }
  return reason instanceof Error ? reason : new Error("Unknown PDF pane error.");
}

function mergeLocalShellUiState(
  assetName: string,
  assetState: PdfAssetState,
): PdfAssetState {
  const state = useAppStore.getState();
  if (state.selectedAssetName !== assetName) {
    return assetState;
  }

  const openMarkdownPaths = getOpenMarkdownPathsForAsset(state, assetName);
  const currentMarkdownPath =
    state.currentMarkdownPath && openMarkdownPaths.includes(state.currentMarkdownPath)
      ? state.currentMarkdownPath
      : null;

  return {
    ...assetState,
    uiState: {
      ...assetState.uiState,
      currentMarkdownPath,
      openMarkdownPaths: dedupePaths([
        ...openMarkdownPaths,
        ...(currentMarkdownPath ? [currentMarkdownPath] : []),
      ]),
      sidebarCollapsed: state.sidebarCollapsed,
      sidebarCollapsedNodeIds: [...(state.sidebarCollapsedNodeIdsByAsset[assetName] ?? [])],
      markdownScrollFractions: {
        ...(state.markdownScrollFractionsByAsset[assetName] ?? {}),
      },
      sidebarWidthRatio: state.sidebarWidthRatio,
      rightRailWidthRatio: state.rightRailWidthRatio,
    },
  };
}
