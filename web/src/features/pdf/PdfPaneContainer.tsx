import { useEffect, useState, type ReactNode } from "react";

import type { PdfNavigationRequest } from "../../app/store/appStore.types";
import { useAppStore } from "../../app/store/appStore";
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
    pdfFileUrl,
    loading,
    mutating,
    error,
    refresh,
    createBlock,
    deleteBlock,
    deleteGroup,
    previewMergeMarkdown,
    mergeGroup,
    updateSelection,
    patchUiState,
  } = usePdfDocument(assetName);
  const pdfNavigationRequest = useAppStore((state) => state.pdfNavigationRequest);
  const consumePdfNavigationRequest = useAppStore((state) => state.consumePdfNavigationRequest);
  const [pendingNavigationRequest, setPendingNavigationRequest] =
    useState<PdfNavigationRequest | null>(null);

  useEffect(() => {
    onAssetStateChange?.(assetState);
  }, [assetState, onAssetStateChange]);

  useEffect(() => {
    setPendingNavigationRequest(null);
  }, [assetName]);

  useEffect(() => {
    if (!pdfNavigationRequest || pdfNavigationRequest.assetName !== assetName) {
      return;
    }

    setPendingNavigationRequest(pdfNavigationRequest);
    consumePdfNavigationRequest();
  }, [assetName, consumePdfNavigationRequest, pdfNavigationRequest]);

  return (
    <PdfPane
      appMode={appMode}
      assetName={assetName}
      assetState={assetState}
      busy={mutating}
      className={className}
      error={error?.message ?? null}
      pdfFileUrl={pdfFileUrl}
      initialCompressSelection={initialCompressSelection}
      loading={loading}
      metadata={metadata}
      onCompressSelectionChange={onCompressSelectionChange}
      onCreateBlock={createBlock}
      onDeleteBlock={(block) => deleteBlock(block.blockId)}
      onDeleteGroup={deleteGroup}
      onPreviewMergeMarkdown={previewMergeMarkdown}
      onMergeSelection={mergeGroup}
      onGroupedBlockActivate={onGroupedBlockActivate}
      onRefresh={() => {
        void refresh();
      }}
      onNavigationHandled={(request) => {
        setPendingNavigationRequest((current) =>
          current?.nonce === request.nonce ? null : current,
        );
      }}
      onSelectionChange={updateSelection}
      onUiStateChange={(patch) => {
        void patchUiState(patch);
      }}
      navigationRequest={pendingNavigationRequest}
      toolbarSlot={toolbarSlot}
    />
  );
}
