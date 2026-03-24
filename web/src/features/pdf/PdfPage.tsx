import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

import { DragSelectionOverlay, type SelectionRect } from "../selection";
import { BLOCK_VISUAL_STYLES } from "./constants";
import {
  collectContainedTextBoxesForPage,
  getBlockFractionRect,
  normalizedPageRectToCssRect,
} from "./geometry";
import {
  ensureRenderedBitmap,
  hasExactCachedBitmap,
  peekCachedBitmap,
  type PdfRenderQuality,
} from "./renderCache";
import type {
  AppMode,
  NormalizedPageRect,
  PdfBlockRecord,
  PdfPageLayout,
  PdfTextBox,
} from "./types";

interface PdfPageProps {
  assetName: string;
  appMode: AppMode;
  pageLayout: PdfPageLayout;
  blocks: PdfBlockRecord[];
  textBoxes: PdfTextBox[];
  disabledContentItemIndexes: number[];
  hoveredBlockId: number | null;
  hoveredGroupIdx: number | null;
  selectionOrderByBlock: Map<number, number>;
  compressSelection: NormalizedPageRect | null;
  mergeSelectionAction: {
    pageIndex: number;
    rect: NormalizedPageRect;
    totalSelectedCount: number;
  } | null;
  mergeSelectionBusy: boolean;
  dragPreviewRect: SelectionRect | null;
  dragPreviewActive: boolean;
  busy: boolean;
  onSurfacePointerDown: (event: ReactPointerEvent<HTMLElement>, pageIndex: number) => void;
  onSurfacePointerMove: (event: ReactPointerEvent<HTMLElement>) => void;
  onSurfacePointerUp: (event: ReactPointerEvent<HTMLElement>) => void;
  onSurfacePointerCancel: () => void;
  onSurfaceDoubleClick?: (pageIndex: number) => void;
  onBlockClick: (block: PdfBlockRecord) => void;
  onBlockDelete: (block: PdfBlockRecord) => void;
  onTextBoxToggle: (itemIndex: number) => void;
  onMergeSelection: () => void;
  onBlockHoverEnter: (block: PdfBlockRecord) => void;
  onBlockHoverLeave: (block: PdfBlockRecord) => void;
  pdfDocument: PDFDocumentProxy | null;
  renderQuality: PdfRenderQuality;
  zoom: number;
}

export function PdfPage({
  assetName,
  appMode,
  pageLayout,
  blocks,
  textBoxes,
  disabledContentItemIndexes,
  hoveredBlockId,
  hoveredGroupIdx,
  selectionOrderByBlock,
  compressSelection,
  mergeSelectionAction,
  mergeSelectionBusy,
  dragPreviewRect,
  dragPreviewActive,
  busy,
  onSurfacePointerDown,
  onSurfacePointerMove,
  onSurfacePointerUp,
  onSurfacePointerCancel,
  onSurfaceDoubleClick,
  onBlockClick,
  onBlockDelete,
  onTextBoxToggle,
  onMergeSelection,
  onBlockHoverEnter,
  onBlockHoverLeave,
  pdfDocument,
  renderQuality,
  zoom,
}: PdfPageProps) {
  const canvasRefs = useRef<[HTMLCanvasElement | null, HTMLCanvasElement | null]>([null, null]);
  const activeBufferIndexRef = useRef(0);
  const displayedBitmapKeyRef = useRef<string | null>(null);
  const [rendered, setRendered] = useState(false);
  const [renderingPreview, setRenderingPreview] = useState(false);

  function swapVisibleBuffer(nextVisibleIndex: number): void {
    activeBufferIndexRef.current = nextVisibleIndex;
    canvasRefs.current.forEach((canvas, index) => {
      if (!canvas) {
        return;
      }
      applyBufferVisibility(canvas, index === nextVisibleIndex);
    });
  }

  useEffect(() => {
    const [primaryCanvas, secondaryCanvas] = canvasRefs.current;
    if (!primaryCanvas || !secondaryCanvas || !pdfDocument) {
      setRendered(false);
      setRenderingPreview(false);
      displayedBitmapKeyRef.current = null;
      return;
    }

    const controller = new AbortController();
    const pixelRatio = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
    const request = {
      assetName,
      pageIndex: pageLayout.pageIndex,
      pageWidth: pageLayout.width,
      pageHeight: pageLayout.height,
      zoom,
      pixelRatio,
      quality: renderQuality,
    } as const;
    const visibleCanvas = canvasRefs.current[activeBufferIndexRef.current];
    const hiddenCanvas = canvasRefs.current[(activeBufferIndexRef.current + 1) % 2];
    if (!visibleCanvas || !hiddenCanvas) {
      return;
    }

    const cached = peekCachedBitmap(request);
    const hasExactCached = hasExactCachedBitmap(request);
    if (cached) {
      if (displayedBitmapKeyRef.current !== cached.key) {
        const visibleContext = visibleCanvas.getContext("2d");
        if (visibleContext) {
          drawBitmapToCanvas(
            visibleCanvas,
            visibleContext,
            cached.bitmap,
            pageLayout.width,
            pageLayout.height,
          );
          displayedBitmapKeyRef.current = cached.key;
          setRendered(true);
          setRenderingPreview(cached.quality !== "final");
        }
      }
      if (hasExactCached && (cached.quality === "final" || renderQuality !== "final")) {
        return () => {
          controller.abort();
        };
      }
    } else {
      setRendered(false);
      setRenderingPreview(renderQuality === "preview");
      displayedBitmapKeyRef.current = null;
    }

    void ensureRenderedBitmap(pdfDocument, request, {
      priority: renderQuality === "final" ? 100 : 50,
      signal: controller.signal,
    })
      .then((entry) => {
        if (controller.signal.aborted) {
          return;
        }
        const nextVisibleIndex = (activeBufferIndexRef.current + 1) % 2;
        const nextVisibleCanvas = canvasRefs.current[nextVisibleIndex];
        const nextVisibleContext = nextVisibleCanvas?.getContext("2d");
        if (!nextVisibleCanvas || !nextVisibleContext) {
          return;
        }
        drawBitmapToCanvas(
          nextVisibleCanvas,
          nextVisibleContext,
          entry.bitmap,
          pageLayout.width,
          pageLayout.height,
        );
        displayedBitmapKeyRef.current = entry.key;
        swapVisibleBuffer(nextVisibleIndex);
        setRendered(true);
        setRenderingPreview(entry.quality !== "final");
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          console.warn("Failed to render PDF page", err);
        }
      });

    return () => {
      controller.abort();
    };
  }, [
    assetName,
    pdfDocument,
    pageLayout.pageIndex,
    pageLayout.width,
    pageLayout.height,
    renderQuality,
    zoom,
  ]);

  const pageStyle: CSSProperties = {
    top: pageLayout.top,
    width: pageLayout.width,
    height: pageLayout.height,
  };

  const compressRect = compressSelection ? normalizedPageRectToCssRect(compressSelection, pageLayout) : null;
  const mergeActionStyle =
    mergeSelectionAction != null
      ? buildMergeActionStyle(normalizedPageRectToCssRect(mergeSelectionAction.rect, pageLayout))
      : null;
  const containedTextBoxes = collectContainedTextBoxesForPage(
    pageLayout.pageIndex,
    blocks,
    textBoxes,
  );
  const disabledTextBoxIndexes = new Set(disabledContentItemIndexes);

  return (
    <article className="pdf-page" style={pageStyle}>
      <div className="pdf-page__frame">
        <canvas
          ref={(element) => {
            canvasRefs.current[0] = element;
            if (element) {
              applyBufferVisibility(element, 0 === activeBufferIndexRef.current);
            }
          }}
          aria-hidden="true"
          className="pdf-page__canvas"
          data-buffer-index="0"
          role="presentation"
        />
        <canvas
          ref={(element) => {
            canvasRefs.current[1] = element;
            if (element) {
              applyBufferVisibility(element, 1 === activeBufferIndexRef.current);
            }
          }}
          aria-hidden="true"
          className="pdf-page__canvas"
          data-buffer-index="1"
          role="presentation"
        />
        {!rendered ? (
          <div className="pdf-page__loading">
            <span>Rendering page {pageLayout.pageIndex + 1}</span>
          </div>
        ) : renderingPreview ? (
          <div className="pdf-page__loading pdf-page__loading--preview">
            <span>Previewing page {pageLayout.pageIndex + 1}</span>
          </div>
        ) : null}
        <div className="pdf-page__label">Page {pageLayout.pageIndex + 1}</div>
        <div
          className={joinClasses(
            "pdf-page__surface",
            appMode === "compress" ? "pdf-page__surface--compress" : undefined,
          )}
          onPointerCancel={() => {
            onSurfacePointerCancel();
          }}
          onPointerDown={(event) => {
            onSurfacePointerDown(event, pageLayout.pageIndex);
          }}
          onPointerMove={(event) => {
            onSurfacePointerMove(event);
          }}
          onPointerUp={(event) => {
            onSurfacePointerUp(event);
          }}
          onDoubleClick={(event) => {
            if (busy || event.target !== event.currentTarget) {
              return;
            }

            event.preventDefault();
            onSurfaceDoubleClick?.(pageLayout.pageIndex);
          }}
        >
          {compressRect ? (
            <div
              className="pdf-page__compress"
              style={{
                left: compressRect.x,
                top: compressRect.y,
                width: compressRect.width,
                height: compressRect.height,
              }}
            />
          ) : null}
          {mergeSelectionAction && mergeActionStyle ? (
            <div
              className="pdf-page__mergeActions"
              style={mergeActionStyle}
            >
              <button
                className="pdf-page__mergeAction pdf-page__mergeAction--merge"
                disabled={mergeSelectionBusy}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onMergeSelection();
                }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                }}
                title={
                  mergeSelectionAction.totalSelectedCount > 1
                    ? `Auto-fill markdown from ${mergeSelectionAction.totalSelectedCount} selected blocks`
                    : "Auto-fill markdown from the selected block"
                }
                type="button"
              >
                Merge
              </button>
            </div>
          ) : null}
          {blocks.map((block) => {
            const variant = blockVariant(block, hoveredBlockId, hoveredGroupIdx, selectionOrderByBlock);
            const rect = normalizedPageRectToCssRect(getBlockFractionRect(block), pageLayout);
            const selectionIndex = selectionOrderByBlock.get(block.blockId) ?? null;
            const visual = BLOCK_VISUAL_STYLES[variant];
            const style: CSSProperties = {
              left: rect.x,
              top: rect.y,
              width: rect.width,
              height: rect.height,
              opacity: visual.opacity ?? 1,
              ["--pdf-block-border" as string]: visual.borderColor,
              ["--pdf-block-background" as string]: visual.backgroundColor,
              ["--pdf-block-style" as string]: visual.borderStyle,
              ["--pdf-block-width" as string]: `${visual.borderWidth}px`,
              ["--pdf-badge-background" as string]: visual.badgeBackground,
              ["--pdf-badge-color" as string]: visual.badgeColor,
            };
            const title =
              block.groupIdx != null
                ? `Group ${block.groupIdx} block ${block.blockId}`
                : selectionIndex != null
                  ? `Selected block ${block.blockId}`
                  : `Block ${block.blockId}`;

            return (
              <button
                aria-label={title}
                className={joinClasses(
                  "pdf-block",
                  variant === "selected" ? "pdf-block--selected" : undefined,
                  block.groupIdx != null ? "pdf-block--grouped" : undefined,
                )}
                key={block.blockId}
                onClick={(event) => {
                  event.stopPropagation();
                  onBlockClick(block);
                }}
                onContextMenu={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onBlockDelete(block);
                }}
                onMouseEnter={() => {
                  onBlockHoverEnter(block);
                }}
                onMouseLeave={() => {
                  onBlockHoverLeave(block);
                }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                }}
                style={style}
                title={title}
                type="button"
              >
                {selectionIndex != null ? (
                  <span className="pdf-block__badge">{selectionIndex}</span>
                ) : block.groupIdx != null ? (
                  <span className="pdf-block__badge">{`G${block.groupIdx}`}</span>
                ) : null}
                <span className="pdf-block__caption">{title}</span>
                <span
                  className="pdf-block__delete"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onBlockDelete(block);
                  }}
                  role="button"
                  tabIndex={-1}
                >
                  {block.groupIdx != null ? "Delete group" : "Delete"}
                </span>
              </button>
            );
          })}
          {containedTextBoxes.map((textBox, index) => {
            const rect = normalizedPageRectToCssRect(textBox.fractionRect, pageLayout);
            const disabled = disabledTextBoxIndexes.has(textBox.itemIndex);
            const label = disabled
              ? `Enable content item ${textBox.itemIndex}`
              : `Disable content item ${textBox.itemIndex}`;

            return (
              <button
                aria-label={label}
                aria-pressed={disabled}
                className={joinClasses(
                  "pdf-page__textBox",
                  disabled ? "pdf-page__textBox--disabled" : undefined,
                )}
                data-testid="pdf-text-box-overlay"
                disabled={busy}
                key={`${textBox.itemIndex}:${textBox.pageIndex}:${textBox.fractionRect.x}:${textBox.fractionRect.y}:${textBox.fractionRect.width}:${textBox.fractionRect.height}:${index}`}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onTextBoxToggle(textBox.itemIndex);
                }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                }}
                style={{
                  left: rect.x,
                  top: rect.y,
                  width: rect.width,
                  height: rect.height,
                }}
                title={label}
                type="button"
              />
            );
          })}
          {dragPreviewActive ? <DragSelectionOverlay rect={dragPreviewRect} /> : null}
          {busy ? <div className="pdf-page__busy">Syncing...</div> : null}
        </div>
      </div>
    </article>
  );
}

function drawBitmapToCanvas(
  canvas: HTMLCanvasElement,
  context: CanvasRenderingContext2D,
  bitmap: HTMLCanvasElement,
  cssWidth: number,
  cssHeight: number,
): void {
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(bitmap, 0, 0, bitmap.width, bitmap.height);
}

function applyBufferVisibility(canvas: HTMLCanvasElement, visible: boolean): void {
  canvas.style.opacity = visible ? "1" : "0";
  canvas.style.visibility = visible ? "visible" : "hidden";
  canvas.style.zIndex = visible ? "1" : "0";
}

function blockVariant(
  block: PdfBlockRecord,
  hoveredBlockId: number | null,
  hoveredGroupIdx: number | null,
  selectionOrderByBlock: Map<number, number>,
): "default" | "selected" | "hover" | "group" | "groupHover" {
  if (selectionOrderByBlock.has(block.blockId)) {
    return "selected";
  }

  if (block.groupIdx != null && hoveredGroupIdx === block.groupIdx) {
    return "groupHover";
  }

  if (hoveredBlockId === block.blockId) {
    return "hover";
  }

  if (block.groupIdx != null) {
    return "group";
  }

  return "default";
}

function joinClasses(...values: Array<string | undefined>): string {
  return values.filter(Boolean).join(" ");
}

function buildMergeActionStyle(
  rect: { x: number; y: number; width: number; height: number },
): CSSProperties {
  return {
    left: rect.x + rect.width / 2,
    top: rect.y + rect.height / 2,
  };
}
