import { useExocortexApi } from "./api/ExocortexApiContext";
import {
  useAssetStateQuery,
  useAssetsQuery,
  useMarkdownTreeQuery,
} from "./api/queries";
import { useAssetUiStateSync } from "./hooks/useAssetUiStateSync";
import { useThemeConfigSync, useThemeDocumentSyncFromStore } from "./hooks/useThemeDocumentSync";
import { WorkbenchShell } from "./shell/WorkbenchShell";
import { fallbackAssets, fallbackMarkdownTree } from "./store/selectors";
import { useSelectedAssetName } from "./hooks/useAppShellSnapshot";

export default function App() {
  const api = useExocortexApi();
  const selectedAssetName = useSelectedAssetName();
  const assetsQuery = useAssetsQuery();
  const assetStateQuery = useAssetStateQuery(selectedAssetName);
  const markdownTreeQuery = useMarkdownTreeQuery(selectedAssetName);
  const assets = fallbackAssets(assetsQuery.data);
  const assetState = assetStateQuery.data ?? null;
  const markdownTree = fallbackMarkdownTree(markdownTreeQuery.data);
  const dataSource = api.mode;

  useThemeDocumentSyncFromStore();
  useThemeConfigSync(api.system);
  useAssetUiStateSync({
    api,
    assets,
    assetState,
  });

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
