import {
  useEffect,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { buildPageImageUrl } from "../../app/api/exocortexApi";
import { DragSelectionOverlay, type SelectionRect } from "../selection";
import { BLOCK_VISUAL_STYLES } from "./constants";
import {
  normalizedPageRectToCssRect,
  toCssRect,
} from "./geometry";
import type {
  AppMode,
  NormalizedPageRect,
  PdfBlockRecord,
  PdfPageLayout,
  PdfPageSize,
} from "./types";

interface PdfPageProps {
  assetName: string;
  appMode: AppMode;
  pageLayout: PdfPageLayout;
  pageSize: PdfPageSize;
  zoom: number;
  renderDpi: number;
  blocks: PdfBlockRecord[];
  hoveredBlockId: number | null;
  hoveredGroupIdx: number | null;
  selectionOrderByBlock: Map<number, number>;
  compressSelection: NormalizedPageRect | null;
  mergeSelectionAction: {
    pageIndex: number;
    rect: {
      x: number;
      y: number;
      width: number;
      height: number;
    };
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
  onBlockClick: (block: PdfBlockRecord) => void;
  onBlockDelete: (block: PdfBlockRecord) => void;
  onMergeSelectionByImage: () => void;
  onMergeSelectionByMarkdown: () => void;
  onBlockHoverEnter: (block: PdfBlockRecord) => void;
  onBlockHoverLeave: (block: PdfBlockRecord) => void;
}

export function PdfPage({
  assetName,
  appMode,
  pageLayout,
  pageSize,
  zoom,
  renderDpi,
  blocks,
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
  onBlockClick,
  onBlockDelete,
  onMergeSelectionByImage,
  onMergeSelectionByMarkdown,
  onBlockHoverEnter,
  onBlockHoverLeave,
}: PdfPageProps) {
  const imageSrc = buildPageImageUrl(assetName, pageLayout.pageIndex, renderDpi);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
  }, [imageSrc]);

  const pageStyle: CSSProperties = {
    top: pageLayout.top,
    width: pageLayout.width,
    height: pageLayout.height,
  };

  const compressRect = compressSelection
    ? normalizedPageRectToCssRect(compressSelection, pageSize)
    : null;
  const mergeActionStyle =
    mergeSelectionAction != null
      ? buildMergeActionStyle(toCssRect(mergeSelectionAction.rect, zoom))
      : null;

  return (
    <article className="pdf-page" style={pageStyle}>
      <div className="pdf-page__frame">
        <img
          alt={`Page ${pageLayout.pageIndex + 1}`}
          className="pdf-page__image"
          draggable={false}
          loading="lazy"
          onLoad={() => {
            setLoaded(true);
          }}
          src={imageSrc}
          style={{
            width: pageLayout.width,
            height: pageLayout.height,
          }}
        />
        {!loaded ? (
          <div className="pdf-page__loading">
            <span>Rendering page {pageLayout.pageIndex + 1}</span>
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
                className="pdf-page__mergeAction pdf-page__mergeAction--image"
                disabled={mergeSelectionBusy}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onMergeSelectionByImage();
                }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                }}
                title={
                  mergeSelectionAction.totalSelectedCount > 1
                    ? `Merge ${mergeSelectionAction.totalSelectedCount} selected blocks by image`
                    : "Create a group from the selected block by image"
                }
                type="button"
              >
                Merge by image
              </button>
              <button
                className="pdf-page__mergeAction pdf-page__mergeAction--markdown"
                disabled={mergeSelectionBusy}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onMergeSelectionByMarkdown();
                }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                }}
                title={
                  mergeSelectionAction.totalSelectedCount > 1
                    ? `Merge ${mergeSelectionAction.totalSelectedCount} selected blocks by markdown`
                    : "Create a group from the selected block by markdown"
                }
                type="button"
              >
                Merge by md
              </button>
            </div>
          ) : null}
          {blocks.map((block) => {
            const variant = blockVariant(block, hoveredBlockId, hoveredGroupIdx, selectionOrderByBlock);
            const rect = toCssRect(block.rect, zoom);
            const selectionIndex = selectionOrderByBlock.get(block.blockId) ?? null;
            const visual = BLOCK_VISUAL_STYLES[variant];
            const style: CSSProperties = {
              left: rect.x,
              top: rect.y,
              width: rect.width,
              height: rect.height,
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
          {dragPreviewActive ? <DragSelectionOverlay rect={dragPreviewRect} /> : null}
          {busy ? <div className="pdf-page__busy">Syncing...</div> : null}
        </div>
      </div>
    </article>
  );
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
