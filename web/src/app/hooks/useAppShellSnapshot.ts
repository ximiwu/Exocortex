import { useAppStore } from "../store/appStore";
import {
  selectAppShellDataSnapshot,
  selectOpenMarkdownPathsForSelectedAsset,
  selectSelectedAssetName,
  selectTheme,
} from "../store/selectors";

export function useThemeMode() {
  return useAppStore(selectTheme);
}

export function useSelectedAssetName() {
  return useAppStore(selectSelectedAssetName);
}

export function useSelectedAssetOpenPaths() {
  return useAppStore(selectOpenMarkdownPathsForSelectedAsset);
}

export function useAppShellDataSnapshot() {
  return useAppStore(selectAppShellDataSnapshot);
}
