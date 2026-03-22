import {
  DEFAULT_MAX_DPI,
  DEFAULT_MIN_DPI,
  PDF_MAX_ZOOM,
  PDF_MIN_ZOOM,
  PDF_PAGE_GAP,
} from "./constants";
import type {
  NormalizedPageRect,
  PdfGroupRecord,
  PdfMetadata,
  PdfPageLayout,
  PdfPageSize,
  PdfRect,
} from "./types";

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function clampZoom(value: number): number {
  return clamp(value, PDF_MIN_ZOOM, PDF_MAX_ZOOM);
}

export function normalizeRect(rect: PdfRect): PdfRect {
  const x = rect.width >= 0 ? rect.x : rect.x + rect.width;
  const y = rect.height >= 0 ? rect.y : rect.y + rect.height;
  const width = Math.abs(rect.width);
  const height = Math.abs(rect.height);

  return { x, y, width, height };
}

export function scaleRect(rect: PdfRect, scale: number): PdfRect {
  const normalized = normalizeRect(rect);

  return {
    x: normalized.x * scale,
    y: normalized.y * scale,
    width: normalized.width * scale,
    height: normalized.height * scale,
  };
}

export function translateRect(rect: PdfRect, offsetX: number, offsetY: number): PdfRect {
  const normalized = normalizeRect(rect);

  return {
    x: normalized.x + offsetX,
    y: normalized.y + offsetY,
    width: normalized.width,
    height: normalized.height,
  };
}

export function clampRectToPage(rect: PdfRect, pageSize: PdfPageSize): PdfRect {
  const normalized = normalizeRect(rect);
  const x = clamp(normalized.x, 0, pageSize.width);
  const y = clamp(normalized.y, 0, pageSize.height);
  const maxWidth = Math.max(0, pageSize.width - x);
  const maxHeight = Math.max(0, pageSize.height - y);

  return {
    x,
    y,
    width: clamp(normalized.width, 0, maxWidth),
    height: clamp(normalized.height, 0, maxHeight),
  };
}

export function toReferenceRect(rect: PdfRect, zoom: number): PdfRect {
  const safeZoom = clampZoom(zoom);
  return scaleRect(rect, 1 / safeZoom);
}

export function toCssRect(rect: PdfRect, zoom: number, top = 0): PdfRect {
  return translateRect(scaleRect(rect, clampZoom(zoom)), 0, top);
}

export function toNormalizedPageRect(rect: PdfRect, pageSize: PdfPageSize): NormalizedPageRect {
  if (pageSize.width <= 0 || pageSize.height <= 0) {
    return { x: 0, y: 0, width: 0, height: 0 };
  }

  const clampedRect = clampRectToPage(rect, pageSize);

  return {
    x: clampedRect.x / pageSize.width,
    y: clampedRect.y / pageSize.height,
    width: clampedRect.width / pageSize.width,
    height: clampedRect.height / pageSize.height,
  };
}

export function normalizedPageRectToCssRect(
  rect: NormalizedPageRect,
  pageSize: PdfPageSize,
  top = 0,
): PdfRect {
  const normalized = normalizeRect(rect);

  return {
    x: normalized.x * pageSize.width,
    y: normalized.y * pageSize.height + top,
    width: normalized.width * pageSize.width,
    height: normalized.height * pageSize.height,
  };
}

export function buildPageLayouts(
  pageSizes: PdfPageSize[],
  zoom: number,
  gap = PDF_PAGE_GAP,
): PdfPageLayout[] {
  const safeZoom = clampZoom(zoom);
  const layouts: PdfPageLayout[] = [];
  let top = 0;

  pageSizes.forEach((pageSize, pageIndex) => {
    const width = pageSize.width * safeZoom;
    const height = pageSize.height * safeZoom;

    layouts.push({
      pageIndex,
      top,
      left: 0,
      width,
      height,
      bottom: top + height,
    });

    top += height + gap;
  });

  return layouts;
}

export function getCanvasHeight(layouts: PdfPageLayout[]): number {
  if (!layouts.length) {
    return 0;
  }

  return layouts[layouts.length - 1].bottom;
}

export function findPageIndexAtOffset(layouts: PdfPageLayout[], offsetY: number): number {
  if (!layouts.length) {
    return 0;
  }

  const firstPage = layouts[0];
  if (offsetY <= firstPage.top) {
    return firstPage.pageIndex;
  }

  for (const layout of layouts) {
    if (offsetY >= layout.top && offsetY < layout.bottom) {
      return layout.pageIndex;
    }
  }

  return layouts[layouts.length - 1].pageIndex;
}

export function findCurrentPage(
  layouts: PdfPageLayout[],
  scrollTop: number,
  viewportHeight: number,
): number {
  const center = scrollTop + viewportHeight / 2;
  return findPageIndexAtOffset(layouts, center);
}

export function findVisiblePageIndexes(
  layouts: PdfPageLayout[],
  scrollTop: number,
  viewportHeight: number,
  bufferPx: number,
): number[] {
  const minY = Math.max(0, scrollTop - bufferPx);
  const maxY = scrollTop + viewportHeight + bufferPx;

  return layouts
    .filter((layout) => layout.bottom >= minY && layout.top <= maxY)
    .map((layout) => layout.pageIndex);
}

export function deriveRenderDpi(
  metadata: PdfMetadata,
  zoom: number,
  devicePixelRatio = 1,
): number {
  const minDpi = metadata.minDpi || DEFAULT_MIN_DPI;
  const maxDpi = metadata.maxDpi || DEFAULT_MAX_DPI;
  const baseDpi = metadata.referenceDpi || metadata.defaultDpi || DEFAULT_MIN_DPI;
  const target = baseDpi * clampZoom(zoom) * Math.max(1, devicePixelRatio);

  return Math.round(clamp(target, minDpi, maxDpi));
}

export function buildSelectionOrderMap(mergeOrder: number[]): Map<number, number> {
  const order = new Map<number, number>();

  mergeOrder.forEach((blockId, index) => {
    order.set(blockId, index + 1);
  });

  return order;
}

export function buildGroupSizeMap(groups: PdfGroupRecord[]): Map<number, number> {
  const result = new Map<number, number>();

  groups.forEach((group) => {
    result.set(group.groupIdx, group.blockIds.length);
  });

  return result;
}
