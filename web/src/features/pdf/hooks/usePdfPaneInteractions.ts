import {
  useCallback,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
  type ChangeEvent,
  type PointerEvent as ReactPointerEvent,
  type UIEvent,
} from "react";

import { useDragSelection } from "../../selection";
import type { PdfNavigationRequest } from "../../../app/store/appStore.types";
import {
  MIN_SELECTION_SIZE,
  PDF_PREHEAT_AHEAD_PAGES,
  PDF_PREHEAT_BEHIND_PAGES,
  PDF_SCROLL_SETTLE_MS,
  PDF_VIEWPORT_BUFFER,
} from "../constants";
import {
  buildGroupSizeMap,
  buildPageLayouts,
  buildSelectionOrderMap,
  clamp,
  clampZoom,
  findCurrentPage,
  findPreheatPageIndexes,
  findVisiblePageIndexes,
  getCanvasHeight,
  toNormalizedPageRect,
} from "../geometry";
import type {
  AppMode,
  NormalizedPageRect,
  PdfAssetState,
  PdfBlockRecord,
  PdfMetadata,
  PdfRect,
  PdfUiState,
} from "../types";

export interface PdfHoverState {
  hoveredBlockId: number | null;
  hoveredGroupIdx: number | null;
}

export interface PdfMergeSelectionAction {
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

interface JumpToRectOptions {
  topOffsetPx?: number;
  leftOffsetPx?: number;
}

interface UsePdfPaneInteractionsInput {
  assetName: string | null;
  assetState: PdfAssetState | null;
  metadata: PdfMetadata | null;
  appMode: AppMode;
  initialCompressSelection: NormalizedPageRect | null;
  onCreateBlock?: (pageIndex: number, rect: PdfRect) => Promise<unknown> | void;
  onDeleteBlock?: (block: PdfBlockRecord) => Promise<unknown> | void;
  onDeleteGroup?: (groupIdx: number) => Promise<unknown> | void;
  onGroupedBlockActivate?: (groupIdx: number, block: PdfBlockRecord) => void;
  onHoverChange?: (hover: PdfHoverState) => void;
  onCompressSelectionChange?: (selection: NormalizedPageRect | null) => void;
  onUiStateChange?: (patch: Partial<PdfUiState>) => void;
  navigationRequest?: PdfNavigationRequest | null;
  onNavigationHandled?: (request: PdfNavigationRequest) => void;
}

const EMPTY_PAGE_SIZES: PdfMetadata["pageSizes"] = [];

export function usePdfPaneInteractions({
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
}: UsePdfPaneInteractionsInput) {
  const appliedUiStateSignatureRef = useRef<string | null>(null);
  const suppressNextScrollEventRef = useRef(false);
  const suppressNextContextMenuRef = useRef(false);
  const panSessionRef = useRef<PanSession | null>(null);
  const [viewportElement, setViewportElement] = useState<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [currentPage, setCurrentPage] = useState(assetState?.uiState.currentPage ?? 1);
  const [zoom, setZoom] = useState(clampZoom(assetState?.uiState.zoom ?? 1));
  const [isScrolling, setIsScrolling] = useState(false);
  const [scrollDirection, setScrollDirection] = useState<1 | -1 | 0>(0);
  const [isRightPanning, setIsRightPanning] = useState(false);
  const [hoverState, setHoverState] = useState<PdfHoverState>({
    hoveredBlockId: null,
    hoveredGroupIdx: null,
  });
  const [compressSelection, setCompressSelection] =
    useState<NormalizedPageRect | null>(initialCompressSelection);
  const scrollStopTimerRef = useRef<number | null>(null);
  const previousScrollTopRef = useRef(0);

  useEffect(() => {
    setHoverState({
      hoveredBlockId: null,
      hoveredGroupIdx: null,
    });
    setCompressSelection(initialCompressSelection);
    setScrollTop(0);
    setIsScrolling(false);
    setScrollDirection(0);
    appliedUiStateSignatureRef.current = null;
  }, [assetName, initialCompressSelection]);

  useEffect(() => {
    return () => {
      if (scrollStopTimerRef.current != null) {
        window.clearTimeout(scrollStopTimerRef.current);
      }
    };
  }, []);

  const viewportRef = useCallback((element: HTMLDivElement | null) => {
    setViewportElement((current) => (current === element ? current : element));
  }, []);

  useEffect(() => {
    const element = viewportElement;
    if (!element) {
      setViewportHeight(0);
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
  }, [viewportElement]);

  const pageSizes = metadata?.pageSizes ?? EMPTY_PAGE_SIZES;
  const layouts = buildPageLayouts(pageSizes, zoom);
  const pageCount = pageSizes.length;
  const canvasWidth = layouts.reduce((maxWidth, layout) => Math.max(maxWidth, layout.width), 0);
  const canvasHeight = getCanvasHeight(layouts);
  const assetUiState = assetState?.uiState ?? null;
  const visiblePageIndexes = findVisiblePageIndexes(
    layouts,
    scrollTop,
    viewportHeight || 1,
    PDF_VIEWPORT_BUFFER,
  );
  const currentPageIndex = Math.max(0, Math.min(pageCount - 1, currentPage - 1));
  const preheatPageIndexes = findPreheatPageIndexes(pageCount, visiblePageIndexes, {
    currentPageIndex,
    direction: scrollDirection,
    aheadCount: PDF_PREHEAT_AHEAD_PAGES,
    behindCount: PDF_PREHEAT_BEHIND_PAGES,
  });
  const selectionOrderByBlock = buildSelectionOrderMap(assetState?.mergeOrder ?? []);
  const groupSizeByIndex = buildGroupSizeMap(assetState?.groups ?? []);
  const mergeSelectionAction = buildMergeSelectionAction(
    assetState?.blocks ?? [],
    assetState?.mergeOrder ?? [],
  );
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

      void onCreateBlock(selection.pageIndex, toNormalizedPageRect(selection.rect, selection.bounds));
    },
  });

  const applyRestoredUiState = useEffectEvent((nextUiState: PdfUiState, signature: string) => {
    const element = viewportElement;
    if (!element || !assetName) {
      return;
    }

    const restoredZoom = clampZoom(nextUiState.zoom ?? 1);
    const nextLayouts = buildPageLayouts(pageSizes, restoredZoom);
    const nextCanvasHeight = getCanvasHeight(nextLayouts);
    const nextCanvasWidth = nextLayouts.reduce(
      (maxWidth, layout) => Math.max(maxWidth, layout.width),
      0,
    );
    const maxScrollTop = Math.max(0, nextCanvasHeight - element.clientHeight);
    const maxScrollLeft = Math.max(0, nextCanvasWidth - element.clientWidth);
    const fractionTop = Math.min(1, Math.max(0, nextUiState.pdfScrollFraction ?? 0));
    const fractionLeft = Math.min(1, Math.max(0, nextUiState.pdfScrollLeftFraction ?? 0));
    const nextScrollTop = maxScrollTop > 0 ? fractionTop * maxScrollTop : 0;
    const nextScrollLeft = maxScrollLeft > 0 ? fractionLeft * maxScrollLeft : 0;

    suppressNextScrollEventRef.current = true;
    element.scrollTop = nextScrollTop;
    element.scrollLeft = nextScrollLeft;
    setScrollTop(nextScrollTop);
    setZoom(restoredZoom);
    setCurrentPage(findCurrentPage(nextLayouts, nextScrollTop, element.clientHeight || 1) + 1);
    appliedUiStateSignatureRef.current = signature;
    requestAnimationFrame(() => {
      suppressNextScrollEventRef.current = false;
    });
  });

  useEffect(() => {
    if (!metadata || !assetUiState || !assetName) {
      return;
    }

    const restoreSignature = buildUiStateSignature(assetName, assetUiState);
    if (appliedUiStateSignatureRef.current === restoreSignature) {
      return;
    }

    const restoredZoom = clampZoom(assetUiState.zoom ?? 1);
    if (!viewportElement || !pageSizes.length || !Number.isFinite(restoredZoom)) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      applyRestoredUiState(assetUiState, restoreSignature);
    });

    return () => cancelAnimationFrame(frame);
  }, [
    applyRestoredUiState,
    assetName,
    assetUiState,
    metadata,
    pageSizes,
    viewportElement,
  ]);

  useEffect(() => {
    if (!pageCount) {
      setCurrentPage(1);
      return;
    }

    setCurrentPage((value) => clamp(value, 1, pageCount));
  }, [pageCount]);

  function handleScrollTopChange(nextScrollTop: number, nextViewportHeight: number): void {
    const nextDirection =
      nextScrollTop > previousScrollTopRef.current
        ? 1
        : nextScrollTop < previousScrollTopRef.current
          ? -1
          : scrollDirection;
    previousScrollTopRef.current = nextScrollTop;
    setScrollTop(nextScrollTop);
    setScrollDirection(nextDirection);
    setIsScrolling(true);
    if (scrollStopTimerRef.current != null) {
      window.clearTimeout(scrollStopTimerRef.current);
    }
    scrollStopTimerRef.current = window.setTimeout(() => {
      setIsScrolling(false);
    }, PDF_SCROLL_SETTLE_MS);

    if (!layouts.length) {
      return;
    }

    const nextCurrentPage = findCurrentPage(layouts, nextScrollTop, nextViewportHeight) + 1;
    if (nextCurrentPage !== currentPage) {
      setCurrentPage(nextCurrentPage);
    }

    const maxScrollTop = Math.max(0, canvasHeight - nextViewportHeight);
    const maxScrollLeft = Math.max(0, canvasWidth - (viewportElement?.clientWidth ?? 0));
    const nextFraction = maxScrollTop > 0 ? nextScrollTop / maxScrollTop : 0;
    const nextLeftFraction =
      maxScrollLeft > 0 ? (viewportElement?.scrollLeft ?? 0) / maxScrollLeft : 0;
    const nextUiState = {
      currentPage: nextCurrentPage,
      zoom,
      pdfScrollFraction: nextFraction,
      pdfScrollLeftFraction: nextLeftFraction,
    };

    if (assetName) {
      appliedUiStateSignatureRef.current = buildUiStateSignature(assetName, nextUiState);
    }

    onUiStateChange?.(nextUiState);
  }

  function handleScroll(event: UIEvent<HTMLDivElement>): void {
    if (suppressNextScrollEventRef.current) {
      return;
    }

    handleScrollTopChange(event.currentTarget.scrollTop, event.currentTarget.clientHeight);
  }

  function beginPan(event: ReactPointerEvent<HTMLDivElement>): void {
    const element = viewportElement;
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
    const element = viewportElement;
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
    const element = viewportElement;
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

  function jumpToPage(pageIndex: number): boolean {
    const element = viewportElement;
    if (!layouts.length || !element) {
      return false;
    }

    const nextPage = clamp(pageIndex, 1, layouts.length);
    const nextUiState = {
      currentPage: nextPage,
      zoom,
      pdfScrollFraction:
        layouts.length > 0
          ? (layouts[nextPage - 1]?.top ?? 0) / Math.max(1, canvasHeight - element.clientHeight)
          : 0,
      pdfScrollLeftFraction:
        canvasWidth > element.clientWidth
          ? element.scrollLeft / Math.max(1, canvasWidth - element.clientWidth)
          : 0,
    };

    setCurrentPage(nextPage);
    if (assetName) {
      appliedUiStateSignatureRef.current = buildUiStateSignature(assetName, nextUiState);
    }
    onUiStateChange?.(nextUiState);
    element.scrollTo({
      top: layouts[nextPage - 1]?.top ?? 0,
      behavior: "smooth",
    });
    return true;
  }

  function jumpToRect(pageIndex: number, rect: PdfRect, options: JumpToRectOptions = {}): boolean {
    const element = viewportElement;
    const layout = layouts[pageIndex];
    if (!layout || !element) {
      return false;
    }

    const topOffsetPx = Math.max(0, options.topOffsetPx ?? 0);
    const leftOffsetPx = Math.max(0, options.leftOffsetPx ?? 0);
    const maxScrollTop = Math.max(0, canvasHeight - element.clientHeight);
    const maxScrollLeft = Math.max(0, canvasWidth - element.clientWidth);
    const nextScrollTop = clamp(
      layout.top + rect.y * layout.height - topOffsetPx,
      0,
      maxScrollTop,
    );
    const nextScrollLeft = clamp(
      layout.left + rect.x * layout.width - leftOffsetPx,
      0,
      maxScrollLeft,
    );
    const nextCurrentPage = pageIndex + 1;
    const nextUiState = {
      currentPage: nextCurrentPage,
      zoom,
      pdfScrollFraction: maxScrollTop > 0 ? nextScrollTop / maxScrollTop : 0,
      pdfScrollLeftFraction: maxScrollLeft > 0 ? nextScrollLeft / maxScrollLeft : 0,
    };

    previousScrollTopRef.current = nextScrollTop;
    if (scrollStopTimerRef.current != null) {
      window.clearTimeout(scrollStopTimerRef.current);
      scrollStopTimerRef.current = null;
    }
    setScrollTop(nextScrollTop);
    setScrollDirection(
      nextScrollTop > scrollTop ? 1 : nextScrollTop < scrollTop ? -1 : scrollDirection,
    );
    setIsScrolling(false);
    setCurrentPage(nextCurrentPage);
    if (assetName) {
      appliedUiStateSignatureRef.current = buildUiStateSignature(assetName, nextUiState);
    }
    onUiStateChange?.(nextUiState);
    element.scrollTo({
      top: nextScrollTop,
      left: nextScrollLeft,
      behavior: "auto",
    });
    return true;
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
    const nextUiState = {
      currentPage,
      zoom: normalizedZoom,
      pdfScrollFraction: assetState?.uiState.pdfScrollFraction ?? 0,
      pdfScrollLeftFraction: assetState?.uiState.pdfScrollLeftFraction ?? 0,
    };

    if (assetName) {
      appliedUiStateSignatureRef.current = buildUiStateSignature(assetName, nextUiState);
    }

    onUiStateChange?.(nextUiState);

    const nextLayouts = buildPageLayouts(metadata.pageSizes, normalizedZoom);
    const nextPageTop = nextLayouts[currentPageIndex]?.top ?? 0;
    requestAnimationFrame(() => {
      viewportElement?.scrollTo({
        top: nextPageTop,
      });
    });
  }

  const handleNavigationRequest = useEffectEvent((request: PdfNavigationRequest) => {
    if (request.assetName !== assetName) {
      return;
    }

    if (jumpToPage(request.page)) {
      onNavigationHandled?.(request);
    }
  });

  useEffect(() => {
    if (!navigationRequest || !assetName || !pageCount) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      handleNavigationRequest(navigationRequest);
    });

    return () => cancelAnimationFrame(frame);
  }, [assetName, handleNavigationRequest, navigationRequest, pageCount, viewportElement]);

  function setHover(hover: PdfHoverState): void {
    setHoverState(hover);
    onHoverChange?.(hover);
  }

  function handleBlockHoverEnter(block: PdfBlockRecord): void {
    if (block.groupIdx == null) {
      return;
    }

    setHover({
      hoveredBlockId: null,
      hoveredGroupIdx: block.groupIdx,
    });
  }

  function handleBlockHoverLeave(block: PdfBlockRecord): void {
    if (block.groupIdx == null) {
      return;
    }

    if (hoverState.hoveredGroupIdx === block.groupIdx) {
      setHover({
        hoveredBlockId: null,
        hoveredGroupIdx: null,
      });
    }
  }

  function handleBlockClick(block: PdfBlockRecord): void {
    if (block.groupIdx != null) {
      onGroupedBlockActivate?.(block.groupIdx, block);
    }
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

  function handleSurfaceDoubleClick(pageIndex: number): void {
    if (appMode === "compress" || !onCreateBlock) {
      return;
    }

    void onCreateBlock(pageIndex, {
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });
  }

  return {
    viewportRef,
    suppressNextContextMenuRef,
    pageSizes,
    layouts,
    pageCount,
    canvasWidth,
    canvasHeight,
    visiblePageIndexes,
    preheatPageIndexes,
    selectionOrderByBlock,
    mergeSelectionAction,
    blocksByPage,
    currentPage,
    currentPageIndex,
    zoom,
    isScrolling,
    isRightPanning,
    hoverState,
    compressSelection,
    dragSelection,
    handleScroll,
    beginPan,
    updatePan,
    endPan,
    cancelPan,
    jumpToRect,
    handlePageInputChange,
    applyZoom,
    handleBlockHoverEnter,
    handleBlockHoverLeave,
    handleBlockClick,
    handleBlockDelete,
    handleSurfaceDoubleClick,
  };
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

function buildMergeSelectionAction(
  blocks: PdfBlockRecord[],
  mergeOrder: number[],
): PdfMergeSelectionAction | null {
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
    rect: anchorBlock.fractionRect ?? anchorBlock.rect ?? { x: 0, y: 0, width: 0, height: 0 },
    totalSelectedCount: selectedBlocks.length,
  };
}

function buildUiStateSignature(
  assetName: string,
  uiState: Pick<PdfUiState, "currentPage" | "zoom" | "pdfScrollFraction" | "pdfScrollLeftFraction">,
): string {
  return JSON.stringify({
    assetName,
    currentPage: Math.max(1, Math.floor(uiState.currentPage || 1)),
    zoom: clampZoom(uiState.zoom ?? 1),
    pdfScrollFraction: normalizeFraction(uiState.pdfScrollFraction ?? 0),
    pdfScrollLeftFraction: normalizeFraction(uiState.pdfScrollLeftFraction ?? 0),
  });
}

function normalizeFraction(value: number): number {
  return Math.round(Math.min(1, Math.max(0, value)) * 1_000_000) / 1_000_000;
}
