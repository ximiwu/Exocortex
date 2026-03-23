import { useEffect } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";

import { useExocortexApi } from "../../../app/api/ExocortexApiContext";
import { queryKeys } from "../../../app/api/exocortexApi";
import { PDF_PAGE_TEXT_BOX_STALE_TIME_MS } from "../constants";
import type { PdfTextBox } from "../types";

interface UsePdfPageTextBoxesInput {
  assetName: string | null;
  enabled?: boolean;
  visiblePageIndexes: number[];
  preheatPageIndexes: number[];
}

export function usePdfPageTextBoxes({
  assetName,
  enabled = true,
  visiblePageIndexes,
  preheatPageIndexes,
}: UsePdfPageTextBoxesInput) {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
  const normalizedVisiblePageIndexes = normalizePageIndexes(visiblePageIndexes);
  const normalizedPreheatPageIndexes = normalizePageIndexes(preheatPageIndexes).filter(
    (pageIndex) => !normalizedVisiblePageIndexes.includes(pageIndex),
  );

  const visibleQueries = useQueries({
    queries: normalizedVisiblePageIndexes.map((pageIndex) => ({
      queryKey: queryKeys.pdfPageTextBoxes(assetName, pageIndex),
      queryFn: () => api.pdf.getPageTextBoxes(assetName!, pageIndex),
      enabled: Boolean(assetName && enabled),
      staleTime: PDF_PAGE_TEXT_BOX_STALE_TIME_MS,
    })),
  });

  useEffect(() => {
    if (!assetName || !enabled) {
      return;
    }

    normalizedPreheatPageIndexes.forEach((pageIndex) => {
      void queryClient.prefetchQuery({
        queryKey: queryKeys.pdfPageTextBoxes(assetName, pageIndex),
        queryFn: () => api.pdf.getPageTextBoxes(assetName, pageIndex),
        staleTime: PDF_PAGE_TEXT_BOX_STALE_TIME_MS,
      });
    });
  }, [api, assetName, enabled, normalizedPreheatPageIndexes, queryClient]);

  const textBoxesByPage = new Map<number, PdfTextBox[]>();
  normalizedVisiblePageIndexes.forEach((pageIndex, index) => {
    textBoxesByPage.set(pageIndex, visibleQueries[index]?.data?.items ?? []);
  });

  return {
    textBoxesByPage,
    loading: visibleQueries.some((query) => query.isPending),
    error: toError(visibleQueries.find((query) => query.error)?.error ?? null),
  };
}

function normalizePageIndexes(pageIndexes: number[]): number[] {
  return Array.from(
    new Set(pageIndexes.filter((pageIndex) => Number.isInteger(pageIndex) && pageIndex >= 0)),
  ).sort((left, right) => left - right);
}

function toError(reason: unknown): Error | null {
  if (!reason) {
    return null;
  }
  return reason instanceof Error ? reason : new Error("Failed to load PDF page text boxes.");
}
