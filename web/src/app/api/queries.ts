import { useQuery, type QueryClient } from "@tanstack/react-query";

import { useExocortexApi } from "./ExocortexApiContext";
import { queryKeys } from "./exocortexApi";

export function useAssetsQuery() {
  const api = useExocortexApi();

  return useQuery({
    queryKey: queryKeys.assets,
    queryFn: () => api.assets.list(),
  });
}

export function useSystemConfigQuery() {
  const api = useExocortexApi();

  return useQuery({
    queryKey: queryKeys.systemConfig,
    queryFn: () => api.system.getConfig(),
  });
}

export function useAssetStateQuery(assetName: string | null) {
  const api = useExocortexApi();

  return useQuery({
    queryKey: queryKeys.assetState(assetName),
    queryFn: () => api.assets.getState(assetName!),
    enabled: Boolean(assetName),
  });
}

export function useMarkdownTreeQuery(assetName: string | null) {
  const api = useExocortexApi();

  return useQuery({
    queryKey: queryKeys.markdownTree(assetName),
    queryFn: () => api.markdown.getTree(assetName!),
    enabled: Boolean(assetName),
  });
}

export function useMarkdownContentQuery(
  assetName: string | null,
  path: string | null,
) {
  const api = useExocortexApi();

  return useQuery({
    queryKey: queryKeys.markdownContent(assetName, path),
    queryFn: () => api.markdown.getContent(assetName!, path!),
    enabled: Boolean(assetName && path),
  });
}

export function usePdfMetadataQuery(assetName: string | null) {
  const api = useExocortexApi();

  return useQuery({
    queryKey: queryKeys.pdfMetadata(assetName),
    queryFn: () => api.pdf.getMetadata(assetName!),
    enabled: Boolean(assetName),
  });
}

export function usePdfPageTextBoxesQuery(assetName: string | null, pageIndex: number | null) {
  const api = useExocortexApi();

  return useQuery({
    queryKey: queryKeys.pdfPageTextBoxes(assetName, pageIndex ?? -1),
    queryFn: () => api.pdf.getPageTextBoxes(assetName!, pageIndex!),
    enabled: Boolean(assetName && pageIndex != null && pageIndex >= 0),
  });
}

export async function invalidateAssetQueries(
  queryClient: QueryClient,
  assetName: string,
  options: {
    includeAssets?: boolean;
    includeMarkdownTree?: boolean;
    includePdfMetadata?: boolean;
  } = {},
): Promise<void> {
  const {
    includeAssets = true,
    includeMarkdownTree = false,
    includePdfMetadata = false,
  } = options;

  const tasks: Array<Promise<void>> = [];

  if (includeAssets) {
    tasks.push(queryClient.invalidateQueries({ queryKey: queryKeys.assets }));
  }

  tasks.push(queryClient.invalidateQueries({ queryKey: queryKeys.assetState(assetName) }));

  if (includeMarkdownTree) {
    tasks.push(
      queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(assetName) }),
    );
  }

  if (includePdfMetadata) {
    tasks.push(
      queryClient.invalidateQueries({ queryKey: queryKeys.pdfMetadata(assetName) }),
    );
  }

  await Promise.all(tasks);
}
