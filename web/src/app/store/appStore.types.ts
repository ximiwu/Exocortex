import type { StateCreator } from "zustand";

import type { AppMode, AssetState, MarkdownTab, Rect, ThemeMode } from "../types";

export type MarkdownOpenSource = "sidebar" | "external";

export interface SidebarRevealTarget {
  assetName: string;
  path: string;
  nonce: number;
}

export interface MarkdownContextMenuRequest {
  x: number;
  y: number;
  nonce: number;
}

export interface GroupDiveRequest {
  assetName: string;
  groupIdx: number;
  nonce: number;
}

export interface AssetDeleteRequest {
  assetName: string;
  nonce: number;
}

export interface PdfNavigationRequest {
  assetName: string;
  page: number;
  nonce: number;
}

export interface ShellUiSlice {
  theme: ThemeMode;
  importDialogOpen: boolean;
  activeTaskPanel: boolean;
  sidebarCollapsed: boolean;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  setImportDialogOpen: (open: boolean) => void;
  setActiveTaskPanel: (active: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export interface WorkspaceTabsSlice {
  currentMarkdownPath: string | null;
  sidebarCollapsedNodeIdsByAsset: Record<string, string[]>;
  sidebarRevealTarget: SidebarRevealTarget | null;
  openTabs: MarkdownTab[];
  markdownScrollFractionsByAsset: Record<string, Record<string, number>>;
  setCurrentMarkdownPath: (path: string | null) => void;
  toggleSidebarNode: (assetName: string, nodeId: string) => void;
  openMarkdownTab: (tab: MarkdownTab, options?: { source?: MarkdownOpenSource }) => void;
  openMarkdownTabs: (tabs: MarkdownTab[], activePath?: string | null) => void;
  closeMarkdownTab: (assetName: string, path: string) => void;
  closeMarkdownTabs: (assetName: string, paths: string[]) => void;
  clearSidebarRevealTarget: () => void;
  rememberMarkdownScroll: (assetName: string, path: string, fraction: number) => void;
}

export interface AssetUiSlice {
  selectedAssetName: string | null;
  sidebarWidthRatio: number;
  rightRailWidthRatio: number;
  setSelectedAssetName: (assetName: string | null) => void;
  setSidebarWidthRatio: (ratio: number) => void;
  setRightRailWidthRatio: (ratio: number) => void;
  hydrateAssetUiState: (assetName: string, state: AssetState) => void;
}

export interface PdfUiSlice {
  currentPage: number;
  zoom: number;
  selectedBlockIds: number[];
  hoveredBlockId: number | null;
  hoveredGroupIdx: number | null;
  appMode: AppMode;
  compressSelection: Rect | null;
  pdfNavigationRequest: PdfNavigationRequest | null;
  setCurrentPage: (page: number) => void;
  setZoom: (zoom: number) => void;
  setAppMode: (mode: AppMode) => void;
  setCompressSelection: (selection: Rect | null) => void;
  requestPdfNavigation: (assetName: string, page: number) => void;
  consumePdfNavigationRequest: () => void;
}

export interface WorkflowUiSlice {
  markdownContextMenuRequest: MarkdownContextMenuRequest | null;
  groupDiveRequest: GroupDiveRequest | null;
  assetDeleteRequest: AssetDeleteRequest | null;
  requestMarkdownContextMenu: (x: number, y: number) => void;
  consumeMarkdownContextMenuRequest: () => void;
  requestGroupDive: (assetName: string, groupIdx: number) => void;
  consumeGroupDiveRequest: () => void;
  requestAssetDelete: (assetName: string) => void;
  consumeAssetDeleteRequest: () => void;
}

export interface AppStoreState
  extends ShellUiSlice,
    WorkspaceTabsSlice,
    AssetUiSlice,
    PdfUiSlice,
    WorkflowUiSlice {}

export type AppStoreSliceCreator<TSlice> = StateCreator<AppStoreState, [], [], TSlice>;
