import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from "pdfjs-dist";

import {
  PDF_MAX_BITMAP_BYTES_BY_DEVICE_MEMORY,
  PDF_MAX_IN_FLIGHT_BYTES_BY_DEVICE_MEMORY,
  PDF_PAGE_CACHE_RADIUS,
  PDF_SINGLE_PAGE_CAP_BYTES_BY_DEVICE_MEMORY,
  PDF_PREVIEW_SCALE,
} from "./constants";

export type PdfRenderQuality = "preview" | "final";
export type PdfRenderPriorityClass = "visible-current" | "visible-adjacent" | "preheat-near" | "offscreen";

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
  estimatedBytes: number;
  renderScale: number;
  lastUsedAt: number;
}

interface RenderQueueItem {
  priority: number;
  priorityClass: PdfRenderPriorityClass;
  sequence: number;
  request: PdfRenderRequest;
  signal?: AbortSignal;
  resolve: (entry: CachedBitmapEntry) => void;
  reject: (reason?: unknown) => void;
}

interface CachedPageEntry {
  assetName: string;
  pageIndex: number;
  promise: Promise<PDFPageProxy>;
  lastUsedAt: number;
}

const MAX_CONCURRENT_RENDERS = 2;
const ZOOM_BUCKET_SIZE = 0.125;
const PIXEL_RATIO_BUCKET_SIZE = 0.5;

const pageCache = new Map<string, CachedPageEntry>();
const bitmapCache = new Map<string, CachedBitmapEntry>();
const inFlightBitmapRenders = new Map<string, Promise<CachedBitmapEntry>>();
const queue: RenderQueueItem[] = [];
let activeRenderCount = 0;
let activeRenderBytes = 0;
let cachedBitmapBytes = 0;
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
    priorityClass?: PdfRenderPriorityClass;
    signal?: AbortSignal;
  },
): Promise<CachedBitmapEntry> {
  const normalizedRequest = normalizeRequestForBudget(request);
  const requestKey = buildBitmapKey(normalizedRequest);
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
      priorityClass: options.priorityClass ?? "offscreen",
      sequence: renderSequence++,
      request: normalizedRequest,
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
    for (const entry of bitmapCache.values()) {
      clearCachedBitmapEntry(entry);
    }
    bitmapCache.clear();
    cachedBitmapBytes = 0;

    for (const entry of pageCache.values()) {
      void entry.promise.then((page) => page.cleanup()).catch(() => undefined);
    }
    pageCache.clear();

    inFlightBitmapRenders.clear();
    queue.length = 0;
    activeRenderBytes = 0;
    return;
  }

  for (const [key, entry] of pageCache.entries()) {
    if (entry.assetName === assetName) {
      pageCache.delete(key);
      void entry.promise.then((page) => page.cleanup()).catch(() => undefined);
    }
  }

  for (const [key, entry] of bitmapCache.entries()) {
    if (entry.assetName === assetName) {
      clearCachedBitmapEntry(entry);
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

export function syncPdfRenderWindow(
  assetName: string,
  visiblePageIndexes: number[],
  preheatPageIndexes: number[],
): void {
  const protectedPages = new Set([...visiblePageIndexes, ...preheatPageIndexes]);

  for (const [key, entry] of bitmapCache.entries()) {
    if (entry.assetName !== assetName) {
      continue;
    }
    if (protectedPages.has(entry.pageIndex)) {
      continue;
    }
    clearCachedBitmapEntry(entry);
    bitmapCache.delete(key);
  }

  const anchor =
    visiblePageIndexes[0] ??
    preheatPageIndexes[0] ??
    null;
  if (anchor == null) {
    clearCachedPagesForAsset(assetName);
    return;
  }

  for (const [key, entry] of pageCache.entries()) {
    if (entry.assetName !== assetName) {
      continue;
    }
    if (Math.abs(entry.pageIndex - anchor) <= PDF_PAGE_CACHE_RADIUS) {
      continue;
    }
    pageCache.delete(key);
    void entry.promise.then((page) => page.cleanup()).catch(() => undefined);
  }
}

async function drainQueue(pdfDocument: PDFDocumentProxy): Promise<void> {
  while (activeRenderCount < MAX_CONCURRENT_RENDERS && queue.length > 0) {
    const next = queue[0];
    if (!next) {
      return;
    }

    if (next.signal?.aborted) {
      queue.shift();
      next.reject(abortError());
      continue;
    }

    const nextBytes = estimateRequestBytes(next.request);
    const maxInFlightBytes = getMaxInFlightBytes();
    if (activeRenderCount > 0 && activeRenderBytes + nextBytes > maxInFlightBytes) {
      return;
    }

    queue.shift();
    activeRenderCount += 1;
    activeRenderBytes += nextBytes;
    void renderAndCache(pdfDocument, next)
      .then(next.resolve, next.reject)
      .finally(() => {
        activeRenderCount = Math.max(0, activeRenderCount - 1);
        activeRenderBytes = Math.max(0, activeRenderBytes - nextBytes);
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

  const renderScale = getCappedRenderScale(page, item.request);
  const viewport = page.getViewport({ scale: renderScale });
  const estimatedBytes = estimateBitmapBytes(viewport.width, viewport.height);
  evictBitmapsForBudget(item.request.assetName, estimatedBytes, item.priorityClass);

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
    estimatedBytes,
    renderScale,
    lastUsedAt: Date.now(),
  };
  cachedBitmapBytes += entry.estimatedBytes;
  bitmapCache.set(entry.key, entry);
  evictBitmapsForBudget(item.request.assetName, 0, item.priorityClass);
  return entry;
}

async function getCachedPage(
  pdfDocument: PDFDocumentProxy,
  assetName: string,
  pageIndex: number,
): Promise<PDFPageProxy> {
  const key = `${assetName}::${pageIndex}`;
  const cachedEntry = pageCache.get(key);
  if (cachedEntry) {
    cachedEntry.lastUsedAt = Date.now();
    return cachedEntry.promise;
  }

  const promise = pdfDocument.getPage(pageIndex + 1);
  pageCache.set(key, {
    assetName,
    pageIndex,
    promise,
    lastUsedAt: Date.now(),
  });
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
  const sizePenalty = entry.estimatedBytes / Math.max(1, 8 * 1024 * 1024);
  return (
    Math.abs(entry.zoomBucket - requestZoomBucket) * 4 +
    Math.abs(entry.pixelRatioBucket - requestPixelRatioBucket) * 2 +
    qualityPenalty +
    sizePenalty
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

function normalizeRequestForBudget(request: PdfRenderRequest): PdfRenderRequest {
  const estimatedBytes = estimateRequestBytes(request);
  const singlePageCapBytes = getSinglePageCapBytes();
  if (estimatedBytes <= singlePageCapBytes || request.quality === "preview") {
    return request;
  }
  return {
    ...request,
    quality: "preview",
  };
}

function estimateRequestBytes(request: PdfRenderRequest): number {
  const renderScale = getEstimatedRenderScale(request);
  return estimateBitmapBytes(request.pageWidth * renderScale, request.pageHeight * renderScale);
}

function estimateBitmapBytes(width: number, height: number): number {
  return Math.max(1, Math.ceil(width)) * Math.max(1, Math.ceil(height)) * 4;
}

function getEstimatedRenderScale(request: PdfRenderRequest): number {
  const qualityScale = request.quality === "preview" ? PDF_PREVIEW_SCALE : 1;
  return Math.max(0.1, request.pixelRatio * qualityScale);
}

function getBaseRenderScale(page: PDFPageProxy, request: PdfRenderRequest): number {
  const baseViewport = page.getViewport({ scale: 1 });
  const baseScale =
    baseViewport.width > 0 ? request.pageWidth / baseViewport.width : 1;
  return Math.max(0.1, baseScale * getEstimatedRenderScale(request));
}

function getCappedRenderScale(page: PDFPageProxy, request: PdfRenderRequest): number {
  const baseScale = getBaseRenderScale(page, request);
  const viewport = page.getViewport({ scale: baseScale });
  const estimatedBytes = estimateBitmapBytes(viewport.width, viewport.height);
  const singlePageCapBytes = getSinglePageCapBytes();
  if (estimatedBytes <= singlePageCapBytes) {
    return baseScale;
  }

  const shrinkRatio = Math.sqrt(singlePageCapBytes / estimatedBytes);
  return Math.max(0.1, baseScale * shrinkRatio);
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

function evictBitmapsForBudget(
  assetName: string,
  requiredBytes: number,
  priorityClass: PdfRenderPriorityClass,
): void {
  const maxBitmapBytes = getMaxBitmapBytes();
  if (cachedBitmapBytes + requiredBytes <= maxBitmapBytes) {
    return;
  }

  const protectedPageIndex = priorityClass === "visible-current" ? findNewestPageIndex(assetName) : null;
  const candidates = Array.from(bitmapCache.values())
    .filter((entry) => entry.assetName === assetName)
    .sort((left, right) => scoreEvictionCandidate(left, right, protectedPageIndex));

  for (const entry of candidates) {
    if (cachedBitmapBytes + requiredBytes <= maxBitmapBytes) {
      return;
    }
    if (protectedPageIndex != null && entry.pageIndex === protectedPageIndex) {
      continue;
    }
    bitmapCache.delete(entry.key);
    clearCachedBitmapEntry(entry);
  }
}

function scoreEvictionCandidate(
  left: CachedBitmapEntry,
  right: CachedBitmapEntry,
  protectedPageIndex: number | null,
): number {
  const leftProtectedPenalty =
    protectedPageIndex != null && left.pageIndex === protectedPageIndex ? 1_000_000 : 0;
  const rightProtectedPenalty =
    protectedPageIndex != null && right.pageIndex === protectedPageIndex ? 1_000_000 : 0;
  const leftQualityPenalty = left.quality === "final" ? 0 : -100;
  const rightQualityPenalty = right.quality === "final" ? 0 : -100;
  return (
    leftProtectedPenalty +
    leftQualityPenalty +
    left.lastUsedAt +
    left.estimatedBytes / (1024 * 1024)
  ) - (
    rightProtectedPenalty +
    rightQualityPenalty +
    right.lastUsedAt +
    right.estimatedBytes / (1024 * 1024)
  );
}

function recoverFromMemoryPressure(assetName: string): void {
  clearQueuedPreheatWork(assetName);
  const candidates = Array.from(bitmapCache.values())
    .filter((entry) => entry.assetName === assetName)
    .sort((left, right) => left.lastUsedAt - right.lastUsedAt);

  for (const entry of candidates) {
    if (bitmapCache.size <= 1) {
      break;
    }
    bitmapCache.delete(entry.key);
    clearCachedBitmapEntry(entry);
  }

  clearCachedPagesForAsset(assetName);
}

function clearQueuedPreheatWork(assetName: string): void {
  for (let index = queue.length - 1; index >= 0; index -= 1) {
    const item = queue[index];
    if (!item || item.request.assetName !== assetName) {
      continue;
    }
    if (item.priorityClass === "visible-current") {
      continue;
    }
    queue.splice(index, 1);
    item.reject(abortError());
  }
}

function clearCachedPagesForAsset(assetName: string): void {
  for (const [key, entry] of pageCache.entries()) {
    if (entry.assetName !== assetName) {
      continue;
    }
    pageCache.delete(key);
    void entry.promise.then((page) => page.cleanup()).catch(() => undefined);
  }
}

function clearCachedBitmapEntry(entry: CachedBitmapEntry): void {
  clearCanvas(entry.bitmap);
  cachedBitmapBytes = Math.max(0, cachedBitmapBytes - entry.estimatedBytes);
}

function findNewestPageIndex(assetName: string): number | null {
  const newest = Array.from(bitmapCache.values())
    .filter((entry) => entry.assetName === assetName)
    .sort((left, right) => right.lastUsedAt - left.lastUsedAt)[0];
  return newest?.pageIndex ?? null;
}

function getDeviceMemoryClass(): number {
  const runtimeNavigator = typeof navigator === "undefined"
    ? null
    : (navigator as Navigator & { deviceMemory?: number });
  if (!runtimeNavigator || typeof runtimeNavigator.deviceMemory !== "number") {
    return 0;
  }
  return runtimeNavigator.deviceMemory;
}

function getMaxBitmapBytes(): number {
  const deviceMemory = getDeviceMemoryClass();
  if (deviceMemory > 8) {
    return PDF_MAX_BITMAP_BYTES_BY_DEVICE_MEMORY.high;
  }
  if (deviceMemory > 4) {
    return PDF_MAX_BITMAP_BYTES_BY_DEVICE_MEMORY.medium;
  }
  return PDF_MAX_BITMAP_BYTES_BY_DEVICE_MEMORY.low;
}

function getMaxInFlightBytes(): number {
  const deviceMemory = getDeviceMemoryClass();
  if (deviceMemory > 8) {
    return PDF_MAX_IN_FLIGHT_BYTES_BY_DEVICE_MEMORY.high;
  }
  if (deviceMemory > 4) {
    return PDF_MAX_IN_FLIGHT_BYTES_BY_DEVICE_MEMORY.medium;
  }
  return PDF_MAX_IN_FLIGHT_BYTES_BY_DEVICE_MEMORY.low;
}

function getSinglePageCapBytes(): number {
  const deviceMemory = getDeviceMemoryClass();
  if (deviceMemory > 8) {
    return PDF_SINGLE_PAGE_CAP_BYTES_BY_DEVICE_MEMORY.high;
  }
  if (deviceMemory > 4) {
    return PDF_SINGLE_PAGE_CAP_BYTES_BY_DEVICE_MEMORY.medium;
  }
  return PDF_SINGLE_PAGE_CAP_BYTES_BY_DEVICE_MEMORY.low;
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
