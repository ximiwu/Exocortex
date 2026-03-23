import type {
  AppStoreSliceCreator,
  WorkflowUiSlice,
} from "../appStore.types";

export const createWorkflowUiSlice: AppStoreSliceCreator<WorkflowUiSlice> = (set) => ({
  markdownContextMenuRequest: null,
  groupDiveRequest: null,
  assetDeleteRequest: null,
  requestMarkdownContextMenu: (x, y) =>
    set({
      markdownContextMenuRequest: {
        x,
        y,
        nonce: Date.now(),
      },
    }),
  consumeMarkdownContextMenuRequest: () => set({ markdownContextMenuRequest: null }),
  requestGroupDive: (assetName, groupIdx) =>
    set({
      groupDiveRequest: {
        assetName,
        groupIdx,
        nonce: Date.now(),
      },
    }),
  consumeGroupDiveRequest: () => set({ groupDiveRequest: null }),
  requestAssetDelete: (assetName) =>
    set({
      assetDeleteRequest: {
        assetName,
        nonce: Date.now(),
      },
    }),
  consumeAssetDeleteRequest: () => set({ assetDeleteRequest: null }),
});
