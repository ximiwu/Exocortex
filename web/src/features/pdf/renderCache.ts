import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from "pdfjs-dist";

export type PdfRenderQuality = "preview" | "final";

export interface PdfRenderRequest {
  assetName: string;
  pageIndex: number;
  pageWidth: number;
  pageHeight: number;
  zoom: number;
  pixelRatio: number;
  quality: PdfRenderQuality;
}

export interface CachedBitmapEntry {
  key: string;
  assetName: string;
  pageIndex: number;
  zoomBucket: number;
  pixelRatioBucket: number;
  quality: PdfRenderQuality;
  width: number;
  height: number;
  bitmap: HTMLCanvasElement;
  lastUsedAt: number;
}

interface RenderQueueItem {
  priority: number;
  sequence: number;
  request: PdfRenderRequest;
  signal?: AbortSignal;
  resolve: (entry: CachedBitmapEntry) => void;
  reject: (reason?: unknown) => void;
}

const MAX_CONCURRENT_RENDERS = 2;
const PREVIEW_SCALE = 0.7;
const ZOOM_BUCKET_SIZE = 0.125;
const PIXEL_RATIO_BUCKET_SIZE = 0.5;
const MEMORY_PRESSURE_RECOVERY_FRACTION = 0.5;

const pageCache = new Map<string, Promise<PDFPageProxy>>();
const bitmapCache = new Map<string, CachedBitmapEntry>();
const inFlightBitmapRenders = new Map<string, Promise<CachedBitmapEntry>>();
const queue: RenderQueueItem[] = [];
let activeRenderCount = 0;
let renderSequence = 0;

export function peekCachedBitmap(
  request: PdfRenderRequest,
): CachedBitmapEntry | null {
  const exactKey = buildBitmapKey(request);
  const exact = bitmapCache.get(exactKey) ?? null;
  if (exact) {
    touchBitmap(exact);
    return exact;
  }

  const candidates = Array.from(bitmapCache.values())
    .filter(
      (entry) =>
        entry.assetName === request.assetName &&
        entry.pageIndex === request.pageIndex,
    )
    .sort((left, right) => compareBitmapEntries(left, right, request));

  const best = candidates[0] ?? null;
  if (best) {
    touchBitmap(best);
  }
  return best;
}

export function hasExactCachedBitmap(request: PdfRenderRequest): boolean {
  return bitmapCache.has(buildBitmapKey(request));
}

export async function ensureRenderedBitmap(
  pdfDocument: PDFDocumentProxy,
  request: PdfRenderRequest,
  options: {
    priority: number;
    signal?: AbortSignal;
  },
): Promise<CachedBitmapEntry> {
  const requestKey = buildBitmapKey(request);
  const cached = bitmapCache.get(requestKey);
  if (cached) {
    touchBitmap(cached);
    return cached;
  }

  const inFlight = inFlightBitmapRenders.get(requestKey);
  if (inFlight) {
    return inFlight;
  }

  const promise = new Promise<CachedBitmapEntry>((resolve, reject) => {
    const item: RenderQueueItem = {
      priority: options.priority,
      sequence: renderSequence++,
      request,
      signal: options.signal,
      resolve,
      reject,
    };

    if (options.signal?.aborted) {
      reject(abortError());
      return;
    }

    options.signal?.addEventListener(
      "abort",
      () => {
        const index = queue.indexOf(item);
        if (index >= 0) {
          queue.splice(index, 1);
        }
        reject(abortError());
      },
      { once: true },
    );

    queue.push(item);
    queue.sort(compareQueueItems);
    void drainQueue(pdfDocument);
  });
  inFlightBitmapRenders.set(requestKey, promise);
  return promise.finally(() => {
    if (inFlightBitmapRenders.get(requestKey) === promise) {
      inFlightBitmapRenders.delete(requestKey);
    }
  });
}

export function clearPdfRenderCache(assetName?: string): void {
  if (!assetName) {
    pageCache.clear();
    bitmapCache.clear();
    inFlightBitmapRenders.clear();
    queue.length = 0;
    return;
  }

  for (const [key, value] of pageCache.entries()) {
    if (key.startsWith(`${assetName}::`)) {
      pageCache.delete(key);
      void value.then((page) => page.cleanup()).catch(() => undefined);
    }
  }

  for (const [key, entry] of bitmapCache.entries()) {
    if (entry.assetName === assetName) {
      clearCanvas(entry.bitmap);
      bitmapCache.delete(key);
    }
  }

  for (const key of Array.from(inFlightBitmapRenders.keys())) {
    if (key.startsWith(`${assetName}::`)) {
      inFlightBitmapRenders.delete(key);
    }
  }

  for (let index = queue.length - 1; index >= 0; index -= 1) {
    if (queue[index]?.request.assetName === assetName) {
      queue.splice(index, 1);
    }
  }
}

async function drainQueue(pdfDocument: PDFDocumentProxy): Promise<void> {
  while (activeRenderCount < MAX_CONCURRENT_RENDERS && queue.length > 0) {
    const next = queue.shift();
    if (!next) {
      return;
    }

    if (next.signal?.aborted) {
      next.reject(abortError());
      continue;
    }

    activeRenderCount += 1;
    void renderAndCache(pdfDocument, next)
      .then(next.resolve, next.reject)
      .finally(() => {
        activeRenderCount = Math.max(0, activeRenderCount - 1);
        void drainQueue(pdfDocument);
      });
  }
}

async function renderAndCache(
  pdfDocument: PDFDocumentProxy,
  item: RenderQueueItem,
): Promise<CachedBitmapEntry> {
  const page = await getCachedPage(pdfDocument, item.request.assetName, item.request.pageIndex);
  if (item.signal?.aborted) {
    throw abortError();
  }

  const renderScale = getRenderScale(page, item.request);
  const viewport = page.getViewport({ scale: renderScale });
  const bitmap = await renderBitmap(page, viewport, item.signal, item.request.assetName);

  const entry: CachedBitmapEntry = {
    key: buildBitmapKey(item.request),
    assetName: item.request.assetName,
    pageIndex: item.request.pageIndex,
    zoomBucket: bucketValue(item.request.zoom, ZOOM_BUCKET_SIZE),
    pixelRatioBucket: bucketValue(item.request.pixelRatio, PIXEL_RATIO_BUCKET_SIZE),
    quality: item.request.quality,
    width: bitmap.width,
    height: bitmap.height,
    bitmap,
    lastUsedAt: Date.now(),
  };
  bitmapCache.set(entry.key, entry);
  return entry;
}

async function getCachedPage(
  pdfDocument: PDFDocumentProxy,
  assetName: string,
  pageIndex: number,
): Promise<PDFPageProxy> {
  const key = `${assetName}::${pageIndex}`;
  const cachedPromise = pageCache.get(key);
  if (cachedPromise) {
    return cachedPromise;
  }

  const promise = pdfDocument.getPage(pageIndex + 1);
  pageCache.set(key, promise);
  return promise;
}

function touchBitmap(entry: CachedBitmapEntry): void {
  entry.lastUsedAt = Date.now();
}

function compareBitmapEntries(
  left: CachedBitmapEntry,
  right: CachedBitmapEntry,
  request: PdfRenderRequest,
): number {
  const requestZoomBucket = bucketValue(request.zoom, ZOOM_BUCKET_SIZE);
  const requestPixelRatioBucket = bucketValue(
    request.pixelRatio,
    PIXEL_RATIO_BUCKET_SIZE,
  );
  const leftScore = scoreBitmapEntry(left, request, requestZoomBucket, requestPixelRatioBucket);
  const rightScore = scoreBitmapEntry(right, request, requestZoomBucket, requestPixelRatioBucket);
  return leftScore - rightScore;
}

function scoreBitmapEntry(
  entry: CachedBitmapEntry,
  request: PdfRenderRequest,
  requestZoomBucket: number,
  requestPixelRatioBucket: number,
): number {
  const qualityPenalty =
    request.quality === "final" && entry.quality !== "final" ? 10 : 0;
  return (
    Math.abs(entry.zoomBucket - requestZoomBucket) * 4 +
    Math.abs(entry.pixelRatioBucket - requestPixelRatioBucket) * 2 +
    qualityPenalty
  );
}

function compareQueueItems(left: RenderQueueItem, right: RenderQueueItem): number {
  if (left.priority !== right.priority) {
    return right.priority - left.priority;
  }
  return left.sequence - right.sequence;
}

function buildBitmapKey(request: PdfRenderRequest): string {
  return [
    request.assetName,
    request.pageIndex,
    bucketValue(request.zoom, ZOOM_BUCKET_SIZE),
    bucketValue(request.pixelRatio, PIXEL_RATIO_BUCKET_SIZE),
    request.quality,
  ].join("::");
}

function bucketValue(value: number, bucketSize: number): number {
  return Math.round(value / bucketSize) * bucketSize;
}

function getRenderScale(page: PDFPageProxy, request: PdfRenderRequest): number {
  const baseViewport = page.getViewport({ scale: 1 });
  const baseScale =
    baseViewport.width > 0 ? request.pageWidth / baseViewport.width : 1;
  const qualityScale = request.quality === "preview" ? PREVIEW_SCALE : 1;
  return Math.max(0.1, baseScale * request.pixelRatio * qualityScale);
}

async function renderBitmap(
  page: PDFPageProxy,
  viewport: ReturnType<PDFPageProxy["getViewport"]>,
  signal: AbortSignal | undefined,
  assetName: string,
): Promise<HTMLCanvasElement> {
  try {
    return await renderBitmapOnce(page, viewport, signal);
  } catch (error) {
    if (isRenderCancelled(error) || !isMemoryPressureError(error)) {
      throw error;
    }

    recoverFromMemoryPressure(assetName);
    return renderBitmapOnce(page, viewport, signal);
  }
}

async function renderBitmapOnce(
  page: PDFPageProxy,
  viewport: ReturnType<PDFPageProxy["getViewport"]>,
  signal: AbortSignal | undefined,
): Promise<HTMLCanvasElement> {
  const bitmap = document.createElement("canvas");
  const context = bitmap.getContext("2d", {
    alpha: false,
    willReadFrequently: false,
  });
  if (!context) {
    throw new Error("Unable to create PDF render context.");
  }

  bitmap.width = Math.max(1, Math.ceil(viewport.width));
  bitmap.height = Math.max(1, Math.ceil(viewport.height));

  let renderTask: RenderTask | null = null;
  try {
    renderTask = page.render({
      canvas: bitmap,
      canvasContext: context,
      viewport,
    });
    signal?.addEventListener(
      "abort",
      () => {
        renderTask?.cancel();
      },
      { once: true },
    );
    await renderTask.promise;
    return bitmap;
  } catch (error) {
    if (isRenderCancelled(error)) {
      throw abortError();
    }
    clearCanvas(bitmap);
    throw error;
  }
}

function recoverFromMemoryPressure(assetName: string): void {
  const assetEntries = Array.from(bitmapCache.values())
    .filter((entry) => entry.assetName === assetName)
    .sort((left, right) => left.lastUsedAt - right.lastUsedAt);
  const removeCount = Math.max(
    1,
    Math.floor(assetEntries.length * MEMORY_PRESSURE_RECOVERY_FRACTION),
  );

  for (const entry of assetEntries.slice(0, removeCount)) {
    clearCanvas(entry.bitmap);
    bitmapCache.delete(entry.key);
  }

  const pageKeys = Array.from(pageCache.keys()).filter((key) =>
    key.startsWith(`${assetName}::`),
  );
  const pageRemoveCount = Math.max(
    1,
    Math.floor(pageKeys.length * MEMORY_PRESSURE_RECOVERY_FRACTION),
  );
  for (const key of pageKeys.slice(0, pageRemoveCount)) {
    const promise = pageCache.get(key);
    pageCache.delete(key);
    void promise?.then((cachedPage) => cachedPage.cleanup()).catch(() => undefined);
  }
}

function clearCanvas(canvas: HTMLCanvasElement): void {
  const context = canvas.getContext("2d");
  context?.clearRect(0, 0, canvas.width, canvas.height);
  canvas.width = 1;
  canvas.height = 1;
}

function abortError(): Error {
  return new DOMException("PDF render request cancelled.", "AbortError");
}

function isRenderCancelled(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.name === "RenderingCancelledException" || error.name === "AbortError")
  );
}

function isMemoryPressureError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return (
    error.name === "RangeError" ||
    message.includes("memory") ||
    message.includes("allocation") ||
    message.includes("out of memory")
  );
}
