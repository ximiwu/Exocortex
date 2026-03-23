import { useEffect } from "react";
import type {
  MutableRefObject,
  PointerEvent as ReactPointerEvent,
  Ref,
  UIEvent,
} from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

import type { SelectionRect } from "../../selection";
import { PdfPage } from "../PdfPage";
import type { PdfHoverState, PdfMergeSelectionAction } from "../hooks/usePdfPaneInteractions";
import { ensureRenderedBitmap } from "../renderCache";
import type {
  AppMode,
  NormalizedPageRect,
  PdfBlockRecord,
  PdfPageLayout,
  PdfPageSize,
  PdfTextBox,
} from "../types";

interface PdfDragSelectionState {
  activePageIndex: number | null;
  previewRect: SelectionRect | null;
  beginDrag: (event: ReactPointerEvent<HTMLElement>, pageIndex: number) => void;
  updateDrag: (event: ReactPointerEvent<HTMLElement>) => void;
  endDrag: (event: ReactPointerEvent<HTMLElement>) => void;
  cancelDrag: () => void;
}

interface PdfPaneViewportProps {
  assetName: string;
  pageSizes: PdfPageSize[];
  layouts: PdfPageLayout[];
  visiblePageIndexes: number[];
  preheatPageIndexes: number[];
  canvasWidth: number;
  canvasHeight: number;
  busy: boolean;
  mergeSelectionBusy: boolean;
  appMode: AppMode;
  zoom: number;
  isScrolling: boolean;
  isRightPanning: boolean;
  blocksByPage: Map<number, PdfBlockRecord[]>;
  textBoxesByPage: Map<number, PdfTextBox[]>;
  selectionOrderByBlock: Map<number, number>;
  mergeSelectionAction: PdfMergeSelectionAction | null;
  compressSelection: NormalizedPageRect | null;
  hoverState: PdfHoverState;
  dragSelection: PdfDragSelectionState;
  pdfDocument: PDFDocumentProxy | null;
  viewportRef: Ref<HTMLDivElement>;
  suppressNextContextMenuRef: MutableRefObject<boolean>;
  onScroll: (event: UIEvent<HTMLDivElement>) => void;
  onBeginPan: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onUpdatePan: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onEndPan: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onCancelPan: () => void;
  onBlockClick: (block: PdfBlockRecord) => void;
  onBlockDelete: (block: PdfBlockRecord) => void;
  onBlockHoverEnter: (block: PdfBlockRecord) => void;
  onBlockHoverLeave: (block: PdfBlockRecord) => void;
  onMergeSelection: () => void;
}

export function PdfPaneViewport({
  assetName,
  pageSizes,
  layouts,
  visiblePageIndexes,
  preheatPageIndexes,
  canvasWidth,
  canvasHeight,
  busy,
  mergeSelectionBusy,
  appMode,
  zoom,
  isScrolling,
  isRightPanning,
  blocksByPage,
  textBoxesByPage,
  selectionOrderByBlock,
  mergeSelectionAction,
  compressSelection,
  hoverState,
  dragSelection,
  pdfDocument,
  viewportRef,
  suppressNextContextMenuRef,
  onScroll,
  onBeginPan,
  onUpdatePan,
  onEndPan,
  onCancelPan,
  onBlockClick,
  onBlockDelete,
  onBlockHoverEnter,
  onBlockHoverLeave,
  onMergeSelection,
}: PdfPaneViewportProps) {
  useEffect(() => {
    if (!pdfDocument) {
      return;
    }

    const pixelRatio = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
    const immediateSet = new Set([...visiblePageIndexes, ...preheatPageIndexes]);
    const abortControllers = layouts.map((layout, pageIndex) => {
      if (!pageSizes[pageIndex] || immediateSet.has(pageIndex)) {
        return null;
      }

      const controller = new AbortController();
      void ensureRenderedBitmap(
        pdfDocument,
        {
          assetName,
          pageIndex,
          pageWidth: layout.width,
          pageHeight: layout.height,
          zoom,
          pixelRatio,
          quality: "final",
        },
        {
          priority: -100 - pageIndex,
          signal: controller.signal,
        },
      ).catch(() => undefined);
      return controller;
    });

    return () => {
      abortControllers.forEach((controller) => controller?.abort());
    };
  }, [
    assetName,
    layouts,
    pageSizes,
    pdfDocument,
    preheatPageIndexes,
    visiblePageIndexes,
    zoom,
  ]);

  useEffect(() => {
    if (!pdfDocument) {
      return;
    }

    const pixelRatio = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
    const abortControllers = preheatPageIndexes.map((pageIndex, order) => {
      const layout = layouts[pageIndex];
      if (!layout) {
        return null;
      }

      const controller = new AbortController();
      void ensureRenderedBitmap(
        pdfDocument,
        {
          assetName,
          pageIndex,
          pageWidth: layout.width,
          pageHeight: layout.height,
          zoom,
          pixelRatio,
          quality: isScrolling ? "preview" : order < 2 ? "final" : "preview",
        },
        {
          priority: isScrolling ? -order - 1 : 10 - order,
          signal: controller.signal,
        },
      ).catch(() => undefined);
      return controller;
    });

    return () => {
      abortControllers.forEach((controller) => controller?.abort());
    };
  }, [assetName, isScrolling, layouts, pdfDocument, preheatPageIndexes, zoom]);

  if (!pageSizes.length) {
    return <div className="pdf-pane__empty">No PDF metadata is available for this asset yet.</div>;
  }

  return (
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
        onCancelPan();
      }}
      onPointerDown={(event) => {
        onBeginPan(event);
      }}
      onPointerMove={(event) => {
        onUpdatePan(event);
      }}
      onPointerUp={(event) => {
        onEndPan(event);
      }}
      onScroll={onScroll}
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

          if (!layout || !pageSizes[pageIndex]) {
            return null;
          }

          return (
            <PdfPage
              assetName={assetName}
              appMode={appMode}
              blocks={blocksByPage.get(pageIndex) ?? []}
              textBoxes={textBoxesByPage.get(pageIndex) ?? []}
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
              mergeSelectionBusy={mergeSelectionBusy}
              onBlockClick={onBlockClick}
              onBlockDelete={onBlockDelete}
              onBlockHoverEnter={onBlockHoverEnter}
              onBlockHoverLeave={onBlockHoverLeave}
              onMergeSelection={onMergeSelection}
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
              selectionOrderByBlock={selectionOrderByBlock}
              pdfDocument={pdfDocument}
              renderQuality="final"
              zoom={zoom}
            />
          );
        })}
      </div>
    </div>
  );
}

function joinClasses(...values: Array<string | undefined>): string {
  return values.filter(Boolean).join(" ");
}
