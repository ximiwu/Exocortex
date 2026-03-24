import { useQuery } from "@tanstack/react-query";

import { useExocortexApi } from "../../../app/api/ExocortexApiContext";
import { queryKeys } from "../../../app/api/exocortexApi";
import { PDF_PAGE_TEXT_BOX_STALE_TIME_MS } from "../constants";
import type { PdfSearchMatch } from "../types";

interface UsePdfContentSearchInput {
  assetName: string | null;
  query: string;
  disabledContentItemIndexes: number[];
  enabled?: boolean;
}

export function usePdfContentSearch({
  assetName,
  query,
  disabledContentItemIndexes,
  enabled = true,
}: UsePdfContentSearchInput) {
  const api = useExocortexApi();
  const normalizedQuery = query.trim();
  const disabledSignature = buildDisabledSignature(disabledContentItemIndexes);
  const searchQuery = useQuery({
    queryKey: queryKeys.pdfSearch(assetName, normalizedQuery, disabledSignature),
    queryFn: () => api.pdf.searchContent(assetName!, normalizedQuery),
    enabled: Boolean(assetName && enabled && normalizedQuery),
    staleTime: PDF_PAGE_TEXT_BOX_STALE_TIME_MS,
  });

  return {
    query: searchQuery.data?.query ?? normalizedQuery,
    matches: searchQuery.data?.matches ?? ([] as PdfSearchMatch[]),
    loading: searchQuery.isPending,
    error: toError(searchQuery.error),
  };
}

function buildDisabledSignature(disabledContentItemIndexes: number[]): string {
  return Array.from(
    new Set(
      disabledContentItemIndexes.filter(
        (value) => Number.isInteger(value) && value > 0,
      ),
    ),
  )
    .sort((left, right) => left - right)
    .join(",");
}

function toError(reason: unknown): Error | null {
  if (!reason) {
    return null;
  }
  return reason instanceof Error ? reason : new Error("Failed to search PDF content.");
}
