import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import type { PdfNavigationRequest } from "../../app/store/appStore.types";
import { PDF_SEARCH_SCROLL_TOP_OFFSET_PX, PDF_ZOOM_STEP } from "./constants";
import { PdfMarkdownMergeDialog } from "./components/PdfMarkdownMergeDialog";
import { PdfPaneToolbar } from "./components/PdfPaneToolbar";
import { PdfPaneViewport } from "./components/PdfPaneViewport";
import { usePdfContentSearch } from "./hooks/usePdfContentSearch";
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
  PdfSearchMatch,
  PdfUiState,
} from "./types";
import "./PdfPane.css";

type HoverState = PdfHoverState;
type SearchDirection = -1 | 1;

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
  onDisabledContentItemsChange?: (disabledContentItemIndexes: number[]) => Promise<unknown> | void;
  onPreviewMergeMarkdown?: (blockIds: number[]) => Promise<{ markdown: string; warning?: string | null }> | { markdown: string; warning?: string | null };
  onMergeSelection?: (
    blockIds: number[],
    options?: {
      markdownContent?: string | null;
      groupIdx?: number | null;
    },
  ) => Promise<unknown> | void;
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
  onDisabledContentItemsChange,
  onPreviewMergeMarkdown,
  onMergeSelection,
  onGroupedBlockActivate,
  onHoverChange,
  onCompressSelectionChange,
  onUiStateChange,
  navigationRequest = null,
  onNavigationHandled,
}: PdfPaneProps) {
  const [markdownMergeDialogOpen, setMarkdownMergeDialogOpen] = useState(false);
  const [markdownMergeInput, setMarkdownMergeInput] = useState("");
  const [markdownPrefillPending, setMarkdownPrefillPending] = useState(false);
  const [markdownPrefillError, setMarkdownPrefillError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearchMatchIndex, setActiveSearchMatchIndex] = useState<number | null>(null);
  const previousAssetNameRef = useRef<string | null>(null);
  const markdownPreviewRequestIdRef = useRef(0);
  const previousSearchMatchesRef = useRef<PdfSearchMatch[]>([]);

  const interactions = usePdfPaneInteractions({
    assetName,
    assetState,
    metadata,
    appMode,
    initialCompressSelection,
    onCreateBlock,
    onDeleteBlock,
    onDeleteGroup,
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
  const contentSearch = usePdfContentSearch({
    assetName,
    query: searchQuery,
    disabledContentItemIndexes: assetState?.disabledContentItemIndexes ?? [],
    enabled: Boolean(assetName),
  });
  const paneLoading = loading || pdfDocumentLoading;
  const paneError = error ?? pdfDocumentError?.message ?? pageTextBoxes.error?.message ?? null;
  const normalizedSearchQuery = searchQuery.trim();
  const searchMatches = contentSearch.matches;
  const searchStatus = buildSearchStatus({
    query: normalizedSearchQuery,
    matches: searchMatches,
    activeMatchIndex: activeSearchMatchIndex,
    loading: contentSearch.loading,
    error: contentSearch.error,
  });
  const searchUpIndex = resolveSearchNavigationIndex(
    searchMatches,
    activeSearchMatchIndex,
    interactions.currentPage,
    -1,
  );
  const searchDownIndex = resolveSearchNavigationIndex(
    searchMatches,
    activeSearchMatchIndex,
    interactions.currentPage,
    1,
  );
  const activeSearchMatch =
    activeSearchMatchIndex != null ? searchMatches[activeSearchMatchIndex] ?? null : null;

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
    setMarkdownPrefillPending(false);
    setMarkdownPrefillError(null);
    markdownPreviewRequestIdRef.current += 1;
    previousSearchMatchesRef.current = [];
    setSearchQuery("");
    setActiveSearchMatchIndex(null);
  }, [assetName, initialCompressSelection]);

  useEffect(() => {
    const previousMatches = previousSearchMatchesRef.current;
    setActiveSearchMatchIndex((current) => {
      if (current == null) {
        return null;
      }

      const previousActiveMatch = previousMatches[current];
      if (!previousActiveMatch) {
        return null;
      }

      const nextIndex = searchMatches.findIndex(
        (match) => match.itemIndex === previousActiveMatch.itemIndex,
      );
      return nextIndex >= 0 ? nextIndex : null;
    });
    previousSearchMatchesRef.current = searchMatches;
  }, [searchMatches]);

  function cancelMarkdownPreview(): void {
    markdownPreviewRequestIdRef.current += 1;
    setMarkdownPrefillPending(false);
  }

  function handleMergeOpen(): void {
    if (!assetState?.mergeOrder.length || !onMergeSelection || !onPreviewMergeMarkdown) {
      return;
    }

    const requestId = markdownPreviewRequestIdRef.current + 1;
    markdownPreviewRequestIdRef.current = requestId;
    setMarkdownMergeDialogOpen(true);
    setMarkdownPrefillPending(true);
    setMarkdownPrefillError(null);

    void Promise.resolve(onPreviewMergeMarkdown(assetState.mergeOrder))
      .then((response) => {
        if (markdownPreviewRequestIdRef.current !== requestId) {
          return;
        }

        setMarkdownMergeInput(response.markdown);
        setMarkdownPrefillPending(false);
        if (response.warning) {
          window.alert(response.warning);
        }
      })
      .catch((reason: unknown) => {
        if (markdownPreviewRequestIdRef.current !== requestId) {
          return;
        }

        setMarkdownPrefillPending(false);
        setMarkdownPrefillError(toErrorMessage(reason));
      });
  }

  function handleMarkdownMergeConfirm(): void {
    if (!assetState?.mergeOrder.length || !onMergeSelection || markdownPrefillPending) {
      return;
    }

    void onMergeSelection(assetState.mergeOrder, {
      markdownContent: markdownMergeInput,
    });
    cancelMarkdownPreview();
    setMarkdownPrefillError(null);
    setMarkdownMergeDialogOpen(false);
    setMarkdownMergeInput("");
  }

  function handleTextBoxToggle(itemIndex: number): void {
    if (!assetState || !onDisabledContentItemsChange) {
      return;
    }

    const disabledContentItemIndexes = new Set(assetState.disabledContentItemIndexes);
    if (disabledContentItemIndexes.has(itemIndex)) {
      disabledContentItemIndexes.delete(itemIndex);
    } else {
      disabledContentItemIndexes.add(itemIndex);
    }

    void onDisabledContentItemsChange(Array.from(disabledContentItemIndexes).sort((left, right) => left - right));
  }

  const dialogBusy = busy || markdownPrefillPending;

  function handleSearchInputChange(event: ChangeEvent<HTMLInputElement>): void {
    setSearchQuery(event.target.value);
    setActiveSearchMatchIndex(null);
  }

  function handleSearchInputKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key !== "Enter") {
      return;
    }

    event.preventDefault();
    handleSearchNavigate(event.shiftKey ? -1 : 1);
  }

  function handleSearchNavigate(direction: SearchDirection): void {
    const nextIndex = resolveSearchNavigationIndex(
      searchMatches,
      activeSearchMatchIndex,
      interactions.currentPage,
      direction,
    );
    if (nextIndex == null) {
      return;
    }

    const nextMatch = searchMatches[nextIndex];
    if (!nextMatch) {
      return;
    }

    if (
      !interactions.jumpToRect(nextMatch.pageIndex, nextMatch.fractionRect, {
        topOffsetPx: PDF_SEARCH_SCROLL_TOP_OFFSET_PX,
        leftOffsetPx: PDF_SEARCH_SCROLL_TOP_OFFSET_PX,
      })
    ) {
      return;
    }

    setActiveSearchMatchIndex(nextIndex);
  }

  return (
    <section className={joinClasses("pdf-pane", className)}>
      <PdfPaneToolbar
        canNavigateSearchDown={searchDownIndex != null && !contentSearch.loading}
        canNavigateSearchUp={searchUpIndex != null && !contentSearch.loading}
        currentPage={interactions.currentPage}
        onPageInputChange={interactions.handlePageInputChange}
        onSearchDown={() => {
          handleSearchNavigate(1);
        }}
        onSearchInputChange={handleSearchInputChange}
        onSearchInputKeyDown={handleSearchInputKeyDown}
        onRefresh={() => {
          onRefresh?.();
        }}
        onSearchUp={() => {
          handleSearchNavigate(-1);
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
        onZoomCommit={(nextZoom) => {
          interactions.applyZoom(nextZoom);
        }}
        pageCount={interactions.pageCount}
        searchBusy={contentSearch.loading}
        searchError={Boolean(contentSearch.error && normalizedSearchQuery)}
        searchQuery={searchQuery}
        searchStatus={searchStatus}
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
          activeSearchMatch={activeSearchMatch}
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
          onTextBoxToggle={handleTextBoxToggle}
          onEndPan={interactions.endPan}
          onMergeSelection={handleMergeOpen}
          onSurfaceDoubleClick={interactions.handleSurfaceDoubleClick}
          onScroll={interactions.handleScroll}
          onUpdatePan={interactions.updatePan}
          pageSizes={interactions.pageSizes}
          preheatPageIndexes={interactions.preheatPageIndexes}
          mergeSelectionBusy={dialogBusy}
          disabledContentItemIndexes={assetState?.disabledContentItemIndexes ?? []}
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
        busy={dialogBusy}
        error={markdownPrefillError}
        markdown={markdownMergeInput}
        onClose={() => {
          cancelMarkdownPreview();
          setMarkdownPrefillError(null);
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

function resolveSearchNavigationIndex(
  matches: PdfSearchMatch[],
  activeMatchIndex: number | null,
  currentPage: number,
  direction: SearchDirection,
): number | null {
  if (!matches.length) {
    return null;
  }

  if (activeMatchIndex != null) {
    const nextIndex = activeMatchIndex + direction;
    return nextIndex >= 0 && nextIndex < matches.length ? nextIndex : null;
  }

  if (direction > 0) {
    const nextIndex = matches.findIndex((match) => match.pageIndex + 1 >= currentPage);
    return nextIndex >= 0 ? nextIndex : null;
  }

  for (let index = matches.length - 1; index >= 0; index -= 1) {
    if ((matches[index]?.pageIndex ?? Number.MAX_SAFE_INTEGER) + 1 <= currentPage) {
      return index;
    }
  }
  return null;
}

function buildSearchStatus({
  query,
  matches,
  activeMatchIndex,
  loading,
  error,
}: {
  query: string;
  matches: PdfSearchMatch[];
  activeMatchIndex: number | null;
  loading: boolean;
  error: Error | null;
}): string {
  if (!query) {
    return "";
  }
  if (loading) {
    return "Searching...";
  }
  if (error) {
    return "Search failed";
  }
  if (!matches.length) {
    return "No results";
  }
  return `${activeMatchIndex == null ? 0 : activeMatchIndex + 1} / ${matches.length}`;
}

function toErrorMessage(reason: unknown): string {
  if (reason instanceof Error && reason.message) {
    return reason.message;
  }
  return "Failed to generate markdown from the current selection.";
}
