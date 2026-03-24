import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";

import {
  clearPdfRenderCache,
  ensureRenderedBitmap,
  peekCachedBitmap,
  syncPdfRenderWindow,
} from "./renderCache";

describe("renderCache", () => {
  beforeEach(() => {
    clearPdfRenderCache();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => {
      return {
        clearRect: vi.fn(),
        drawImage: vi.fn(),
      } as unknown as CanvasRenderingContext2D;
    });
  });

  afterEach(() => {
    clearPdfRenderCache();
    vi.restoreAllMocks();
  });

  it("reuses cached page renders for the same request", async () => {
    const renderPromise = Promise.resolve();
    const render = vi.fn(() => ({ promise: renderPromise, cancel: vi.fn() }));
    const getViewport = vi.fn(({ scale }: { scale: number }) => ({
      width: 400 * scale,
      height: 600 * scale,
    }));
    const page = {
      getViewport,
      render,
      cleanup: vi.fn(),
    } as unknown as PDFPageProxy;
    const getPage = vi.fn(async () => page);
    const pdfDocument = {
      getPage,
    } as unknown as PDFDocumentProxy;

    const request = {
      assetName: "asset-a",
      pageIndex: 0,
      pageWidth: 400,
      pageHeight: 600,
      zoom: 1,
      pixelRatio: 2,
      quality: "final" as const,
    };

    const first = await ensureRenderedBitmap(pdfDocument, request, {
      priority: 100,
    });
    const second = await ensureRenderedBitmap(pdfDocument, request, {
      priority: 100,
    });

    expect(first.bitmap).toBe(second.bitmap);
    expect(getPage).toHaveBeenCalledTimes(1);
    expect(render).toHaveBeenCalledTimes(1);
    expect(peekCachedBitmap(request)?.bitmap).toBe(first.bitmap);
  });

  it("separates caches by asset name", async () => {
    const render = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
    const page = {
      getViewport: ({ scale }: { scale: number }) => ({
        width: 400 * scale,
        height: 600 * scale,
      }),
      render,
      cleanup: vi.fn(),
    } as unknown as PDFPageProxy;
    const getPage = vi.fn(async () => page);
    const pdfDocument = {
      getPage,
    } as unknown as PDFDocumentProxy;

    await ensureRenderedBitmap(
      pdfDocument,
      {
        assetName: "asset-a",
        pageIndex: 0,
        pageWidth: 400,
        pageHeight: 600,
        zoom: 1,
        pixelRatio: 1,
        quality: "preview",
      },
      { priority: 10 },
    );

    expect(
      peekCachedBitmap({
        assetName: "asset-b",
        pageIndex: 0,
        pageWidth: 400,
        pageHeight: 600,
        zoom: 1,
        pixelRatio: 1,
        quality: "preview",
      }),
    ).toBeNull();
  });

  it("deduplicates in-flight renders for the same bitmap request", async () => {
    let resolvePage!: (page: PDFPageProxy) => void;
    const render = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
    const page = {
      getViewport: ({ scale }: { scale: number }) => ({
        width: 400 * scale,
        height: 600 * scale,
      }),
      render,
      cleanup: vi.fn(),
    } as unknown as PDFPageProxy;
    const getPage = vi.fn(
      () =>
        new Promise<PDFPageProxy>((resolve) => {
          resolvePage = resolve;
        }),
    );
    const pdfDocument = {
      getPage,
    } as unknown as PDFDocumentProxy;
    const request = {
      assetName: "asset-a",
      pageIndex: 2,
      pageWidth: 400,
      pageHeight: 600,
      zoom: 1,
      pixelRatio: 1,
      quality: "final" as const,
    };

    const firstPromise = ensureRenderedBitmap(pdfDocument, request, { priority: 1 });
    const secondPromise = ensureRenderedBitmap(pdfDocument, request, { priority: 999 });
    await Promise.resolve();
    resolvePage(page);
    const [first, second] = await Promise.all([firstPromise, secondPromise]);

    expect(first.bitmap).toBe(second.bitmap);
    expect(getPage).toHaveBeenCalledTimes(1);
    expect(render).toHaveBeenCalledTimes(1);
  });

  it("downgrades oversized final renders to preview quality", async () => {
    const render = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
    const getViewport = vi.fn(({ scale }: { scale: number }) => ({
      width: 1200 * scale,
      height: 1800 * scale,
    }));
    const page = {
      getViewport,
      render,
      cleanup: vi.fn(),
    } as unknown as PDFPageProxy;
    const getPage = vi.fn(async () => page);
    const pdfDocument = {
      getPage,
    } as unknown as PDFDocumentProxy;

    const entry = await ensureRenderedBitmap(
      pdfDocument,
      {
        assetName: "asset-a",
        pageIndex: 0,
        pageWidth: 1200,
        pageHeight: 1800,
        zoom: 1,
        pixelRatio: 4,
        quality: "final",
      },
      { priority: 100 },
    );

    expect(entry.quality).toBe("preview");
  });

  it("evicts offscreen bitmaps when syncing the render window", async () => {
    const render = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
    const page = {
      getViewport: ({ scale }: { scale: number }) => ({
        width: 400 * scale,
        height: 600 * scale,
      }),
      render,
      cleanup: vi.fn(),
    } as unknown as PDFPageProxy;
    const getPage = vi.fn(async () => page);
    const pdfDocument = {
      getPage,
    } as unknown as PDFDocumentProxy;

    await ensureRenderedBitmap(
      pdfDocument,
      {
        assetName: "asset-a",
        pageIndex: 0,
        pageWidth: 400,
        pageHeight: 600,
        zoom: 1,
        pixelRatio: 1,
        quality: "final",
      },
      { priority: 100 },
    );
    await ensureRenderedBitmap(
      pdfDocument,
      {
        assetName: "asset-a",
        pageIndex: 1,
        pageWidth: 400,
        pageHeight: 600,
        zoom: 1,
        pixelRatio: 1,
        quality: "preview",
      },
      { priority: 50 },
    );

    syncPdfRenderWindow("asset-a", [0], []);

    expect(
      peekCachedBitmap({
        assetName: "asset-a",
        pageIndex: 1,
        pageWidth: 400,
        pageHeight: 600,
        zoom: 1,
        pixelRatio: 1,
        quality: "preview",
      }),
    ).toBeNull();
    expect(
      peekCachedBitmap({
        assetName: "asset-a",
        pageIndex: 0,
        pageWidth: 400,
        pageHeight: 600,
        zoom: 1,
        pixelRatio: 1,
        quality: "final",
      }),
    ).not.toBeNull();
  });
});
