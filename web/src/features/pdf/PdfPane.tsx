import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type { PdfNavigationRequest } from "../../app/store/appStore.types";
import { PDF_ZOOM_STEP } from "./constants";
import { PdfMarkdownMergeDialog } from "./components/PdfMarkdownMergeDialog";
import { PdfPaneToolbar } from "./components/PdfPaneToolbar";
import { PdfPaneViewport } from "./components/PdfPaneViewport";
import { usePdfPageTextBoxes } from "./hooks/usePdfPageTextBoxes";
import { usePdfPaneInteractions, type PdfHoverState } from "./hooks/usePdfPaneInteractions";
import { usePdfJsDocument } from "./hooks/usePdfJsDocument";
import { clearPdfRenderCache } from "./renderCache";
import type {
  AppMode,
  NormalizedPageRect,
  PdfAssetState,
  PdfBlockRecord,
  PdfMetadata,
  PdfRect,
  PdfUiState,
} from "./types";
import "./PdfPane.css";

type HoverState = PdfHoverState;

export interface PdfPaneProps {
  assetName: string | null;
  assetState: PdfAssetState | null;
  metadata: PdfMetadata | null;
  pdfFileUrl?: string | null;
  loading?: boolean;
  busy?: boolean;
  error?: string | null;
  appMode?: AppMode;
  className?: string;
  toolbarSlot?: ReactNode;
  initialCompressSelection?: NormalizedPageRect | null;
  onRefresh?: () => void;
  onCreateBlock?: (pageIndex: number, rect: PdfRect) => Promise<unknown> | void;
  onDeleteBlock?: (block: PdfBlockRecord) => Promise<unknown> | void;
  onDeleteGroup?: (groupIdx: number) => Promise<unknown> | void;
  onMergeSelection?: (
    blockIds: number[],
    options?: {
      markdownContent?: string | null;
      groupIdx?: number | null;
    },
  ) => Promise<unknown> | void;
  onSelectionChange?: (mergeOrder: number[]) => Promise<unknown> | void;
  onGroupedBlockActivate?: (groupIdx: number, block: PdfBlockRecord) => void;
  onHoverChange?: (hover: HoverState) => void;
  onCompressSelectionChange?: (selection: NormalizedPageRect | null) => void;
  onUiStateChange?: (patch: Partial<PdfUiState>) => void;
  navigationRequest?: PdfNavigationRequest | null;
  onNavigationHandled?: (request: PdfNavigationRequest) => void;
}

export function PdfPane({
  assetName,
  assetState,
  metadata,
  pdfFileUrl = null,
  loading = false,
  busy = false,
  error = null,
  appMode = "normal",
  className,
  toolbarSlot,
  initialCompressSelection = null,
  onRefresh,
  onCreateBlock,
  onDeleteBlock,
  onDeleteGroup,
  onMergeSelection,
  onSelectionChange,
  onGroupedBlockActivate,
  onHoverChange,
  onCompressSelectionChange,
  onUiStateChange,
  navigationRequest = null,
  onNavigationHandled,
}: PdfPaneProps) {
  const [markdownMergeDialogOpen, setMarkdownMergeDialogOpen] = useState(false);
  const [markdownMergeInput, setMarkdownMergeInput] = useState("");
  const previousAssetNameRef = useRef<string | null>(null);

  const interactions = usePdfPaneInteractions({
    assetName,
    assetState,
    metadata,
    appMode,
    initialCompressSelection,
    onCreateBlock,
    onDeleteBlock,
    onDeleteGroup,
    onSelectionChange,
    onGroupedBlockActivate,
    onHoverChange,
    onCompressSelectionChange,
    onUiStateChange,
    navigationRequest,
    onNavigationHandled,
  });

  const {
    pdfDocument,
    loading: pdfDocumentLoading,
    error: pdfDocumentError,
  } = usePdfJsDocument(pdfFileUrl);
  const pageTextBoxes = usePdfPageTextBoxes({
    assetName,
    enabled: Boolean(assetName && metadata),
    visiblePageIndexes: interactions.visiblePageIndexes,
    preheatPageIndexes: interactions.preheatPageIndexes,
  });
  const paneLoading = loading || pdfDocumentLoading;
  const paneError = error ?? pdfDocumentError?.message ?? pageTextBoxes.error?.message ?? null;

  useEffect(() => {
    const previousAssetName = previousAssetNameRef.current;
    if (previousAssetName && previousAssetName !== assetName) {
      clearPdfRenderCache(previousAssetName);
    }
    previousAssetNameRef.current = assetName;
  }, [assetName]);

  useEffect(() => {
    setMarkdownMergeDialogOpen(false);
    setMarkdownMergeInput("");
  }, [assetName, initialCompressSelection]);

  function handleMergeSelectionByMarkdown(): void {
    if (!assetState?.mergeOrder.length || !onMergeSelection) {
      return;
    }

    setMarkdownMergeDialogOpen(true);
  }

  function handleMarkdownMergeConfirm(): void {
    if (!assetState?.mergeOrder.length || !onMergeSelection) {
      return;
    }

    void onMergeSelection(assetState.mergeOrder, {
      markdownContent: markdownMergeInput,
    });
    setMarkdownMergeDialogOpen(false);
    setMarkdownMergeInput("");
  }

  return (
    <section className={joinClasses("pdf-pane", className)}>
      <PdfPaneToolbar
        currentPage={interactions.currentPage}
        onPageInputChange={interactions.handlePageInputChange}
        onRefresh={() => {
          onRefresh?.();
        }}
        onZoomIn={() => {
          interactions.applyZoom(interactions.zoom + PDF_ZOOM_STEP);
        }}
        onZoomOut={() => {
          interactions.applyZoom(interactions.zoom - PDF_ZOOM_STEP);
        }}
        onZoomReset={() => {
          interactions.applyZoom(1);
        }}
        pageCount={interactions.pageCount}
        toolbarSlot={toolbarSlot}
        zoom={interactions.zoom}
      />
      {paneError ? <div className="pdf-pane__error">{paneError}</div> : null}
      {!assetName ? (
        <div className="pdf-pane__empty">Load an asset to inspect PDF pages.</div>
      ) : paneLoading && !assetState ? (
        <div className="pdf-pane__empty">Loading PDF pane...</div>
      ) : !metadata || !interactions.pageCount ? (
        <div className="pdf-pane__empty">No PDF metadata is available for this asset yet.</div>
      ) : (
        <PdfPaneViewport
          assetName={assetName}
          appMode={appMode}
          blocksByPage={interactions.blocksByPage}
          busy={busy}
          canvasHeight={interactions.canvasHeight}
          canvasWidth={interactions.canvasWidth}
          compressSelection={interactions.compressSelection}
          dragSelection={interactions.dragSelection}
          hoverState={interactions.hoverState}
          isScrolling={interactions.isScrolling}
          isRightPanning={interactions.isRightPanning}
          layouts={interactions.layouts}
          mergeSelectionAction={interactions.mergeSelectionAction}
          onBeginPan={interactions.beginPan}
          onBlockClick={interactions.handleBlockClick}
          onBlockDelete={interactions.handleBlockDelete}
          onBlockHoverEnter={interactions.handleBlockHoverEnter}
          onBlockHoverLeave={interactions.handleBlockHoverLeave}
          onCancelPan={interactions.cancelPan}
          onEndPan={interactions.endPan}
          onMergeSelectionByMarkdown={handleMergeSelectionByMarkdown}
          onScroll={interactions.handleScroll}
          onUpdatePan={interactions.updatePan}
          pageSizes={interactions.pageSizes}
          preheatPageIndexes={interactions.preheatPageIndexes}
          selectionOrderByBlock={interactions.selectionOrderByBlock}
          suppressNextContextMenuRef={interactions.suppressNextContextMenuRef}
          textBoxesByPage={pageTextBoxes.textBoxesByPage}
          viewportRef={interactions.viewportRef}
          visiblePageIndexes={interactions.visiblePageIndexes}
          pdfDocument={pdfDocument}
          zoom={interactions.zoom}
        />
      )}
      <PdfMarkdownMergeDialog
        busy={busy}
        markdown={markdownMergeInput}
        onClose={() => {
          setMarkdownMergeDialogOpen(false);
        }}
        onConfirm={handleMarkdownMergeConfirm}
        onMarkdownChange={setMarkdownMergeInput}
        open={markdownMergeDialogOpen}
      />
    </section>
  );
}

function joinClasses(...values: Array<string | undefined>): string {
  return values.filter(Boolean).join(" ");
}
