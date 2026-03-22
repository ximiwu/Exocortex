import { useQueryClient } from "@tanstack/react-query";
import { startTransition, useEffect, useState } from "react";

import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import type {
  PdfAssetState,
  PdfMetadata,
  PdfRect,
  PdfUiState,
} from "./types";

export function usePdfDocument(assetName: string | null) {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
  const [assetState, setAssetState] = useState<PdfAssetState | null>(null);
  const [metadata, setMetadata] = useState<PdfMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (!assetName) {
      setAssetState(null);
      setMetadata(null);
      setLoading(false);
      setMutating(false);
      setError(null);
      return undefined;
    }

    setLoading(true);
    setError(null);

    void Promise.all([api.assets.getState(assetName), api.pdf.getMetadata(assetName)])
      .then(([nextAssetState, nextMetadata]) => {
        if (cancelled) {
          return;
        }

        startTransition(() => {
          setAssetState(nextAssetState);
          setMetadata(nextMetadata);
        });
      })
      .catch((reason: unknown) => {
        if (cancelled) {
          return;
        }

        setError(toError(reason));
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [api.assets, api.pdf, assetName]);

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

  async function refresh(): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    setLoading(true);
    setError(null);

    try {
      const [nextAssetState, nextMetadata] = await Promise.all([
        api.assets.getState(currentAssetName),
        api.pdf.getMetadata(currentAssetName),
      ]);

      startTransition(() => {
        setAssetState(nextAssetState);
        setMetadata(nextMetadata);
      });

      return nextAssetState;
    } catch (reason) {
      setError(toError(reason));
      throw reason;
    } finally {
      setLoading(false);
    }
  }

  async function createBlock(pageIndex: number, rect: PdfRect): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    setMutating(true);
    setError(null);

    try {
      const nextAssetState = await api.pdf.createBlock(currentAssetName, {
        pageIndex,
        rect,
      });
      startTransition(() => {
        setAssetState(nextAssetState);
      });
      invalidateAssetQueries(currentAssetName);
      return nextAssetState;
    } catch (reason) {
      setError(toError(reason));
      throw reason;
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
    setError(null);

    try {
      const nextAssetState = await api.pdf.deleteBlock(currentAssetName, blockId);
      startTransition(() => {
        setAssetState(nextAssetState);
      });
      invalidateAssetQueries(currentAssetName);
      return nextAssetState;
    } catch (reason) {
      setError(toError(reason));
      throw reason;
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
    setError(null);

    try {
      const nextAssetState = await api.pdf.deleteGroup(currentAssetName, groupIdx);
      startTransition(() => {
        setAssetState(nextAssetState);
      });
      invalidateAssetQueries(currentAssetName, {
        includeMarkdownTree: true,
      });
      return nextAssetState;
    } catch (reason) {
      setError(toError(reason));
      throw reason;
    } finally {
      setMutating(false);
    }
  }

  async function updateSelection(mergeOrder: number[]): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName) {
      return null;
    }

    if (assetState) {
      startTransition(() => {
        setAssetState({
          ...assetState,
          mergeOrder: [...mergeOrder],
        });
      });
    }

    setMutating(true);
    setError(null);

    try {
      const nextAssetState = await api.pdf.updateSelection(currentAssetName, mergeOrder);
      startTransition(() => {
        setAssetState(nextAssetState);
      });
      return nextAssetState;
    } catch (reason) {
      setError(toError(reason));
      void refresh();
      throw reason;
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
    setError(null);

    try {
      const nextAssetState = await api.pdf.mergeGroup(currentAssetName, selectedBlockIds, options);
      startTransition(() => {
        setAssetState(nextAssetState);
      });
      invalidateAssetQueries(currentAssetName, {
        includeMarkdownTree: true,
      });
      return nextAssetState;
    } catch (reason) {
      setError(toError(reason));
      throw reason;
    } finally {
      setMutating(false);
    }
  }

  async function patchUiState(
    patch: Partial<PdfUiState>,
  ): Promise<PdfAssetState | null> {
    const currentAssetName = assetName;
    if (!currentAssetName || !assetState) {
      return null;
    }

    const nextUiState: PdfUiState = {
      ...assetState.uiState,
      ...patch,
    };

    startTransition(() => {
      setAssetState({
        ...assetState,
        uiState: nextUiState,
      });
    });

    try {
      const persistedAssetState = await api.pdf.updateUiState(currentAssetName, nextUiState);
      if (persistedAssetState) {
        startTransition(() => {
          setAssetState(persistedAssetState);
        });
        return persistedAssetState;
      }

      return {
        ...assetState,
        uiState: nextUiState,
      };
    } catch (reason) {
      setError(toError(reason));
      void refresh();
      throw reason;
    }
  }

  return {
    assetState,
    metadata,
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

function toError(reason: unknown): Error {
  return reason instanceof Error ? reason : new Error("Unknown PDF pane error.");
}
