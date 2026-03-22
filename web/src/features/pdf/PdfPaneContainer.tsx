import { useEffect, type ReactNode } from "react";

import { PdfPane } from "./PdfPane";
import { usePdfDocument } from "./usePdfDocument";
import type {
  AppMode,
  NormalizedPageRect,
  PdfAssetState,
  PdfBlockRecord,
} from "./types";

export interface PdfPaneContainerProps {
  assetName: string | null;
  appMode?: AppMode;
  className?: string;
  toolbarSlot?: ReactNode;
  initialCompressSelection?: NormalizedPageRect | null;
  onAssetStateChange?: (assetState: PdfAssetState | null) => void;
  onGroupedBlockActivate?: (groupIdx: number, block: PdfBlockRecord) => void;
  onCompressSelectionChange?: (selection: NormalizedPageRect | null) => void;
}

export function PdfPaneContainer({
  assetName,
  appMode = "normal",
  className,
  toolbarSlot,
  initialCompressSelection = null,
  onAssetStateChange,
  onGroupedBlockActivate,
  onCompressSelectionChange,
}: PdfPaneContainerProps) {
  const {
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
  } = usePdfDocument(assetName);

  useEffect(() => {
    onAssetStateChange?.(assetState);
  }, [assetState, onAssetStateChange]);

  return (
    <PdfPane
      appMode={appMode}
      assetName={assetName}
      assetState={assetState}
      busy={mutating}
      className={className}
      error={error?.message ?? null}
      initialCompressSelection={initialCompressSelection}
      loading={loading}
      metadata={metadata}
      onCompressSelectionChange={onCompressSelectionChange}
      onCreateBlock={createBlock}
      onDeleteBlock={(block) => deleteBlock(block.blockId)}
      onDeleteGroup={deleteGroup}
      onMergeSelection={mergeGroup}
      onGroupedBlockActivate={onGroupedBlockActivate}
      onRefresh={() => {
        void refresh();
      }}
      onSelectionChange={updateSelection}
      onUiStateChange={(patch) => {
        void patchUiState(patch);
      }}
      toolbarSlot={toolbarSlot}
    />
  );
}
