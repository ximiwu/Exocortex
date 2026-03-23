import { create } from "zustand";

import type { AppStoreState } from "./appStore.types";
import { createAssetUiSlice } from "./slices/assetUiSlice";
import { createPdfUiSlice } from "./slices/pdfUiSlice";
import { createShellUiSlice } from "./slices/shellUiSlice";
import { createWorkflowUiSlice } from "./slices/workflowUiSlice";
import { createWorkspaceTabsSlice } from "./slices/workspaceTabsSlice";

export const useAppStore = create<AppStoreState>()((...args) => ({
  ...createShellUiSlice(...args),
  ...createWorkspaceTabsSlice(...args),
  ...createAssetUiSlice(...args),
  ...createPdfUiSlice(...args),
  ...createWorkflowUiSlice(...args),
}));

export type {
  AppStoreState,
  AssetDeleteRequest,
  GroupDiveRequest,
  MarkdownContextMenuRequest,
  MarkdownOpenSource,
  SidebarRevealTarget,
} from "./appStore.types";
