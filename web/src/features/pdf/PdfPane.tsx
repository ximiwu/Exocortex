import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type UIEvent,
} from "react";

import { useDragSelection } from "../selection";
import {
  MIN_SELECTION_SIZE,
  PDF_VIEWPORT_BUFFER,
  PDF_ZOOM_STEP,
} from "./constants";
import {
  buildGroupSizeMap,
  buildPageLayouts,
  buildSelectionOrderMap,
  clamp,
  clampZoom,
  deriveRenderDpi,
  findCurrentPage,
  findVisiblePageIndexes,
  getCanvasHeight,
  toNormalizedPageRect,
  toReferenceRect,
} from "./geometry";
import { PdfPage } from "./PdfPage";
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

interface HoverState {
  hoveredBlockId: number | null;
  hoveredGroupIdx: number | null;
}

interface MergeSelectionAction {
  pageIndex: number;
  rect: PdfRect;
  totalSelectedCount: number;
}

interface PanSession {
  pointerId: number;
  originClientX: number;
  originClientY: number;
  originScrollLeft: number;
  originScrollTop: number;
  moved: boolean;
}

export interface PdfPaneProps {
  assetName: string | null;
  assetState: PdfAssetState | null;
  metadata: PdfMetadata | null;
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
}

export function PdfPane({
  assetName,
  assetState,
  metadata,
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
}: PdfPaneProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const restoredScrollContextRef = useRef<string | null>(null);
  const suppressNextScrollEventRef = useRef(false);
  const suppressNextContextMenuRef = useRef(false);
  const panSessionRef = useRef<PanSession | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [currentPage, setCurrentPage] = useState(assetState?.uiState.currentPage ?? 1);
  const [zoom, setZoom] = useState(clampZoom(assetState?.uiState.zoom ?? 1));
  const [isRightPanning, setIsRightPanning] = useState(false);
  const [hoverState, setHoverState] = useState<HoverState>({
    hoveredBlockId: null,
    hoveredGroupIdx: null,
  });
  const [compressSelection, setCompressSelection] =
    useState<NormalizedPageRect | null>(initialCompressSelection);
  const [markdownMergeDialogOpen, setMarkdownMergeDialogOpen] = useState(false);
  const [markdownMergeInput, setMarkdownMergeInput] = useState("");

  useEffect(() => {
    setHoverState({
      hoveredBlockId: null,
      hoveredGroupIdx: null,
    });
    setCompressSelection(initialCompressSelection);
    setMarkdownMergeDialogOpen(false);
    setMarkdownMergeInput("");
    setScrollTop(0);
    restoredScrollContextRef.current = null;
  }, [assetName, initialCompressSelection]);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) {
      return undefined;
    }

    setViewportHeight(element.clientHeight);

    if (typeof ResizeObserver === "undefined") {
      return undefined;
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }

      setViewportHeight(entry.contentRect.height);
    });

    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, []);

  const pageSizes = metadata?.pageSizes ?? [];
  const layouts = buildPageLayouts(pageSizes, zoom);
  const pageCount = pageSizes.length;
  const canvasWidth = layouts.reduce((maxWidth, layout) => Math.max(maxWidth, layout.width), 0);
  const canvasHeight = getCanvasHeight(layouts);
  const assetUiState = assetState?.uiState ?? null;
  const pdfScrollFraction = assetUiState?.pdfScrollFraction ?? 0;
  const pdfScrollLeftFraction = assetUiState?.pdfScrollLeftFraction ?? 0;
  const visiblePageIndexes = findVisiblePageIndexes(
    layouts,
    scrollTop,
    viewportHeight || 1,
    PDF_VIEWPORT_BUFFER,
  );
  const selectionOrderByBlock = buildSelectionOrderMap(assetState?.mergeOrder ?? []);
  const groupSizeByIndex = buildGroupSizeMap(assetState?.groups ?? []);
  const mergeSelectionAction = buildMergeSelectionAction(
    assetState?.blocks ?? [],
    assetState?.mergeOrder ?? [],
  );
  const renderDpi = metadata
    ? deriveRenderDpi(
        metadata,
        zoom,
        typeof window === "undefined" ? 1 : window.devicePixelRatio || 1,
      )
    : 130;
  const blocksByPage = groupBlocksByPage(assetState?.blocks ?? []);
  const dragSelection = useDragSelection({
    enabled: Boolean(assetName && metadata),
    minimumSize: MIN_SELECTION_SIZE,
    onSelectionCommit: (selection) => {
      if (appMode === "compress") {
        const normalizedRect = toNormalizedPageRect(selection.rect, selection.bounds);
        setCompressSelection(normalizedRect);
        onCompressSelectionChange?.(normalizedRect);
        return;
      }

      if (!onCreateBlock) {
        return;
      }

      void onCreateBlock(selection.pageIndex, toReferenceRect(selection.rect, zoom));
    },
  });

  useEffect(() => {
    const element = viewportRef.current;
    if (!element || !metadata || !assetUiState || !assetName) {
      return;
    }

    const restoredZoom = clampZoom(assetUiState.zoom ?? 1);
    const restoreContext = `${assetName}:${restoredZoom}`;
    if (restoredScrollContextRef.current === restoreContext) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      const maxScrollTop = Math.max(0, element.scrollHeight - element.clientHeight);
      const maxScrollLeft = Math.max(0, element.scrollWidth - element.clientWidth);
      const fractionTop = Math.min(1, Math.max(0, pdfScrollFraction));
      const fractionLeft = Math.min(1, Math.max(0, pdfScrollLeftFraction));
      const nextScrollTop = maxScrollTop > 0 ? fractionTop * maxScrollTop : 0;
      const nextScrollLeft = maxScrollLeft > 0 ? fractionLeft * maxScrollLeft : 0;
      suppressNextScrollEventRef.current = true;
      element.scrollTop = nextScrollTop;
      element.scrollLeft = nextScrollLeft;
      setScrollTop(nextScrollTop);
      restoredScrollContextRef.current = restoreContext;
      setCurrentPage(findCurrentPage(layouts, nextScrollTop, element.clientHeight || 1) + 1);
      setZoom(restoredZoom);
      requestAnimationFrame(() => {
        suppressNextScrollEventRef.current = false;
      });
    });

    return () => cancelAnimationFrame(frame);
  }, [
    assetName,
    assetUiState,
    metadata,
    layouts,
    pdfScrollFraction,
    pdfScrollLeftFraction,
  ]);

  useEffect(() => {
    if (!pageCount) {
      setCurrentPage(1);
      return;
    }

    setCurrentPage((value) => clamp(value, 1, pageCount));
  }, [pageCount]);

  function handleScrollTopChange(nextScrollTop: number, nextViewportHeight: number): void {
    setScrollTop(nextScrollTop);
    if (!layouts.length) {
      return;
    }

    const nextCurrentPage = findCurrentPage(layouts, nextScrollTop, nextViewportHeight) + 1;
    if (nextCurrentPage !== currentPage) {
      setCurrentPage(nextCurrentPage);
    }

    const maxScrollTop = Math.max(0, canvasHeight - nextViewportHeight);
    const maxScrollLeft = Math.max(0, canvasWidth - (viewportRef.current?.clientWidth ?? 0));
    const nextFraction = maxScrollTop > 0 ? nextScrollTop / maxScrollTop : 0;
    const nextLeftFraction = maxScrollLeft > 0 ? (viewportRef.current?.scrollLeft ?? 0) / maxScrollLeft : 0;
    onUiStateChange?.({
      currentPage: nextCurrentPage,
      zoom,
      pdfScrollFraction: nextFraction,
      pdfScrollLeftFraction: nextLeftFraction,
    });
  }

  function handleScroll(event: UIEvent<HTMLDivElement>): void {
    if (suppressNextScrollEventRef.current) {
      return;
    }

    handleScrollTopChange(event.currentTarget.scrollTop, event.currentTarget.clientHeight);
  }

  function beginPan(event: ReactPointerEvent<HTMLDivElement>): void {
    const element = viewportRef.current;
    if (!element || event.button !== 2) {
      return;
    }

    suppressNextContextMenuRef.current = false;
    element.setPointerCapture(event.pointerId);
    panSessionRef.current = {
      pointerId: event.pointerId,
      originClientX: event.clientX,
      originClientY: event.clientY,
      originScrollLeft: element.scrollLeft,
      originScrollTop: element.scrollTop,
      moved: false,
    };
    setIsRightPanning(true);
    event.preventDefault();
  }

  function updatePan(event: ReactPointerEvent<HTMLDivElement>): void {
    const element = viewportRef.current;
    const session = panSessionRef.current;
    if (!element || !session || session.pointerId !== event.pointerId) {
      return;
    }

    const deltaX = event.clientX - session.originClientX;
    const deltaY = event.clientY - session.originClientY;
    if (!session.moved && (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2)) {
      session.moved = true;
    }
    panSessionRef.current = session;
    element.scrollLeft = session.originScrollLeft - deltaX;
    element.scrollTop = session.originScrollTop - deltaY;
    event.preventDefault();
  }

  function endPan(event: ReactPointerEvent<HTMLDivElement>): void {
    const element = viewportRef.current;
    const session = panSessionRef.current;
    if (!element || !session || session.pointerId !== event.pointerId) {
      return;
    }

    if (element.hasPointerCapture(event.pointerId)) {
      element.releasePointerCapture(event.pointerId);
    }
    suppressNextContextMenuRef.current = session.moved;
    panSessionRef.current = null;
    setIsRightPanning(false);
    event.preventDefault();
  }

  function cancelPan(): void {
    panSessionRef.current = null;
    setIsRightPanning(false);
  }

  function jumpToPage(pageIndex: number): void {
    if (!layouts.length || !viewportRef.current) {
      return;
    }

    const nextPage = clamp(pageIndex, 1, layouts.length);
    setCurrentPage(nextPage);
    onUiStateChange?.({
      currentPage: nextPage,
      zoom,
      pdfScrollFraction:
        layouts.length > 0 && viewportRef.current
          ? (layouts[nextPage - 1]?.top ?? 0) /
            Math.max(1, canvasHeight - viewportRef.current.clientHeight)
          : 0,
      pdfScrollLeftFraction:
        viewportRef.current && canvasWidth > viewportRef.current.clientWidth
          ? viewportRef.current.scrollLeft / Math.max(1, canvasWidth - viewportRef.current.clientWidth)
          : 0,
    });
    viewportRef.current.scrollTo({
      top: layouts[nextPage - 1]?.top ?? 0,
      behavior: "smooth",
    });
  }

  function handlePageInputChange(event: ChangeEvent<HTMLInputElement>): void {
    if (!pageCount) {
      return;
    }

    const value = Number(event.target.value);
    if (Number.isFinite(value)) {
      jumpToPage(value);
    }
  }

  function applyZoom(nextZoom: number): void {
    const normalizedZoom = clampZoom(nextZoom);
    if (!metadata || normalizedZoom === zoom) {
      return;
    }

    setZoom(normalizedZoom);
    const currentPageIndex = Math.max(0, currentPage - 1);
    onUiStateChange?.({
      currentPage,
      zoom: normalizedZoom,
      pdfScrollFraction: assetState?.uiState.pdfScrollFraction ?? 0,
      pdfScrollLeftFraction: assetState?.uiState.pdfScrollLeftFraction ?? 0,
    });

    const nextLayouts = buildPageLayouts(metadata.pageSizes, normalizedZoom);
    const nextPageTop = nextLayouts[currentPageIndex]?.top ?? 0;
    requestAnimationFrame(() => {
      viewportRef.current?.scrollTo({
        top: nextPageTop,
      });
    });
  }

  function setHover(hover: HoverState): void {
    setHoverState(hover);
    onHoverChange?.(hover);
  }

  function handleBlockHoverEnter(block: PdfBlockRecord): void {
    if (block.groupIdx != null) {
      setHover({
        hoveredBlockId: null,
        hoveredGroupIdx: block.groupIdx,
      });
      return;
    }

    setHover({
      hoveredBlockId: block.blockId,
      hoveredGroupIdx: null,
    });
  }

  function handleBlockHoverLeave(block: PdfBlockRecord): void {
    if (block.groupIdx != null) {
      if (hoverState.hoveredGroupIdx === block.groupIdx) {
        setHover({
          hoveredBlockId: null,
          hoveredGroupIdx: null,
        });
      }
      return;
    }

    if (hoverState.hoveredBlockId === block.blockId) {
      setHover({
        hoveredBlockId: null,
        hoveredGroupIdx: null,
      });
    }
  }

  function handleBlockClick(block: PdfBlockRecord): void {
    if (!assetState) {
      return;
    }

    if (block.groupIdx != null) {
      onGroupedBlockActivate?.(block.groupIdx, block);
      return;
    }

    if (!onSelectionChange) {
      return;
    }

    const nextMergeOrder = toggleMergeOrder(assetState.mergeOrder, block.blockId);
    void onSelectionChange(nextMergeOrder);
  }

  function handleBlockDelete(block: PdfBlockRecord): void {
    if (block.groupIdx != null) {
      if (!onDeleteGroup) {
        return;
      }

      const count = groupSizeByIndex.get(block.groupIdx) ?? 0;
      if (typeof window !== "undefined") {
        const message = count
          ? `Delete group ${block.groupIdx}? This will remove ${count} block(s).`
          : `Delete group ${block.groupIdx}?`;
        if (!window.confirm(message)) {
          return;
        }
      }

      void onDeleteGroup(block.groupIdx);
      return;
    }

    if (!onDeleteBlock) {
      return;
    }

    void onDeleteBlock(block);
  }

  function handleMergeSelectionByImage(): void {
    if (!assetState?.mergeOrder.length || !onMergeSelection) {
      return;
    }

    void onMergeSelection(assetState.mergeOrder);
  }

  function handleMergeSelectionByMarkdown(): void {
    if (!assetState?.mergeOrder.length || !onMergeSelection) {
      return;
    }

    setMarkdownMergeDialogOpen(true);
  }

  function handleMarkdownMergeSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
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
      <header className="pdf-pane__toolbar">
        <div className="pdf-pane__toolbar-group">
          <span className="pdf-pane__label">Page</span>
          <input
            className="pdf-pane__page-input"
            disabled={!pageCount}
            max={pageCount || 1}
            min={1}
            onChange={handlePageInputChange}
            type="number"
            value={pageCount ? currentPage : 1}
          />
          <span className="pdf-pane__meta">{pageCount ? `/ ${pageCount}` : "/ -"}</span>
        </div>
        <div className="pdf-pane__toolbar-group">
          <button
            className="pdf-pane__button"
            onClick={() => {
              applyZoom(zoom - PDF_ZOOM_STEP);
            }}
            type="button"
          >
            -
          </button>
          <span className="pdf-pane__meta">{Math.round(zoom * 100)}%</span>
          <button
            className="pdf-pane__button"
            onClick={() => {
              applyZoom(zoom + PDF_ZOOM_STEP);
            }}
            type="button"
          >
            +
          </button>
          <button
            className="pdf-pane__button pdf-pane__button--secondary"
            onClick={() => {
              applyZoom(1);
            }}
            type="button"
          >
            Reset
          </button>
        </div>
        {toolbarSlot ? (
          <div className="pdf-pane__toolbar-group pdf-pane__toolbar-group--spacer">
            {toolbarSlot}
          </div>
        ) : null}
        <button
          className="pdf-pane__button pdf-pane__button--secondary pdf-pane__button--refresh"
          onClick={() => {
            onRefresh?.();
          }}
          type="button"
        >
          Refresh
        </button>
      </header>
      {error ? <div className="pdf-pane__error">{error}</div> : null}
      {!assetName ? (
        <div className="pdf-pane__empty">Load an asset to inspect PDF pages.</div>
      ) : loading && !assetState ? (
        <div className="pdf-pane__empty">Loading PDF pane...</div>
      ) : !metadata || !pageCount ? (
        <div className="pdf-pane__empty">No PDF metadata is available for this asset yet.</div>
      ) : (
        <div
          className={joinClasses(
            "pdf-pane__viewport",
            isRightPanning ? "pdf-pane__viewport--panning" : undefined,
          )}
          onContextMenu={(event) => {
            if (suppressNextContextMenuRef.current) {
              suppressNextContextMenuRef.current = false;
              event.preventDefault();
            }
          }}
          onPointerCancel={() => {
            cancelPan();
          }}
          onPointerDown={(event) => {
            beginPan(event);
          }}
          onPointerMove={(event) => {
            updatePan(event);
          }}
          onPointerUp={(event) => {
            endPan(event);
          }}
          onScroll={handleScroll}
          ref={viewportRef}
        >
          <div
            className="pdf-pane__canvas"
            style={{
              width: canvasWidth,
              height: canvasHeight,
            }}
          >
            {visiblePageIndexes.map((pageIndex) => {
              const layout = layouts[pageIndex];
              const pageSize = pageSizes[pageIndex];

              if (!layout || !pageSize) {
                return null;
              }

              return (
                <PdfPage
                  appMode={appMode}
                  assetName={assetName}
                  blocks={blocksByPage.get(pageIndex) ?? []}
                  busy={busy}
                  compressSelection={compressSelection}
                  dragPreviewActive={dragSelection.activePageIndex === pageIndex}
                  dragPreviewRect={
                    dragSelection.activePageIndex === pageIndex
                      ? dragSelection.previewRect
                      : null
                  }
                  hoveredBlockId={hoverState.hoveredBlockId}
                  hoveredGroupIdx={hoverState.hoveredGroupIdx}
                  key={pageIndex}
                  mergeSelectionAction={
                    mergeSelectionAction?.pageIndex === pageIndex ? mergeSelectionAction : null
                  }
                  mergeSelectionBusy={busy}
                  onBlockClick={handleBlockClick}
                  onBlockDelete={handleBlockDelete}
                  onBlockHoverEnter={handleBlockHoverEnter}
                  onBlockHoverLeave={handleBlockHoverLeave}
                  onMergeSelectionByImage={handleMergeSelectionByImage}
                  onMergeSelectionByMarkdown={handleMergeSelectionByMarkdown}
                  onSurfacePointerCancel={() => {
                    dragSelection.cancelDrag();
                  }}
                  onSurfacePointerDown={(event, activePageIndex) => {
                    dragSelection.beginDrag(event, activePageIndex);
                  }}
                  onSurfacePointerMove={(event) => {
                    dragSelection.updateDrag(event);
                  }}
                  onSurfacePointerUp={(event) => {
                    dragSelection.endDrag(event);
                  }}
                  pageLayout={layout}
                  pageSize={pageSize}
                  renderDpi={renderDpi}
                  selectionOrderByBlock={selectionOrderByBlock}
                  zoom={zoom}
                />
              );
            })}
          </div>
        </div>
      )}
      {markdownMergeDialogOpen ? (
        <div
          className="modal-scrim"
          onClick={() => {
            if (busy) {
              return;
            }
            setMarkdownMergeDialogOpen(false);
          }}
          role="presentation"
        >
          <form
            className="modal-card modal-card--wide pdf-pane__markdownDialog"
            onClick={(event) => {
              event.stopPropagation();
            }}
            onSubmit={handleMarkdownMergeSubmit}
          >
            <h2>Merge by md</h2>
            <p className="modal-copy">
              输入写入新 group 的 markdown 内容，确认后会按已选 block 创建分组并保存到
              <code>content.md</code>。
            </p>
            <label className="form-field">
              <span>Markdown</span>
              <textarea
                autoFocus
                className="pdf-pane__markdownInput"
                disabled={busy}
                onChange={(event) => {
                  setMarkdownMergeInput(event.target.value);
                }}
                rows={12}
                value={markdownMergeInput}
              />
            </label>
            <div className="modal-actions">
              <button
                className="pdf-pane__button pdf-pane__button--secondary"
                disabled={busy}
                onClick={() => {
                  setMarkdownMergeDialogOpen(false);
                }}
                type="button"
              >
                Cancel
              </button>
              <button className="pdf-pane__button" disabled={busy} type="submit">
                Confirm
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </section>
  );
}

function groupBlocksByPage(blocks: PdfBlockRecord[]): Map<number, PdfBlockRecord[]> {
  const blocksByPage = new Map<number, PdfBlockRecord[]>();

  blocks.forEach((block) => {
    const current = blocksByPage.get(block.pageIndex);
    if (current) {
      current.push(block);
      return;
    }

    blocksByPage.set(block.pageIndex, [block]);
  });

  return blocksByPage;
}

function toggleMergeOrder(mergeOrder: number[], blockId: number): number[] {
  if (mergeOrder.includes(blockId)) {
    return mergeOrder.filter((id) => id !== blockId);
  }

  return [...mergeOrder, blockId];
}

function joinClasses(...values: Array<string | undefined>): string {
  return values.filter(Boolean).join(" ");
}

function buildMergeSelectionAction(
  blocks: PdfBlockRecord[],
  mergeOrder: number[],
): MergeSelectionAction | null {
  if (!mergeOrder.length) {
    return null;
  }

  const blockMap = new Map(blocks.map((block) => [block.blockId, block]));
  const selectedBlocks = mergeOrder
    .map((blockId) => blockMap.get(blockId))
    .filter((block): block is PdfBlockRecord => Boolean(block && block.groupIdx == null));

  if (!selectedBlocks.length) {
    return null;
  }

  const anchorBlock = selectedBlocks[selectedBlocks.length - 1];
  if (!anchorBlock) {
    return null;
  }

  return {
    pageIndex: anchorBlock.pageIndex,
    rect: anchorBlock.rect,
    totalSelectedCount: selectedBlocks.length,
  };
}
