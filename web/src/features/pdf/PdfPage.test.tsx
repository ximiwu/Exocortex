import { fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";

import { clearPdfRenderCache, ensureRenderedBitmap } from "./renderCache";
import { PdfPage } from "./PdfPage";

describe("PdfPage", () => {
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

  it("reuses cached bitmaps without requesting the page again", async () => {
    const renderPage = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
    const page = {
      getViewport: ({ scale }: { scale: number }) => ({
        width: 400 * scale,
        height: 600 * scale,
      }),
      render: renderPage,
      cleanup: vi.fn(),
    } as unknown as PDFPageProxy;
    const getPage = vi.fn(async () => page);
    const pdfDocument = { getPage } as unknown as PDFDocumentProxy;

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

    expect(getPage).toHaveBeenCalledTimes(1);
    expect(renderPage).toHaveBeenCalledTimes(1);

    render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[]}
        textBoxes={[]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={() => undefined}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={pdfDocument}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    await waitFor(() => {
      expect(renderPage).toHaveBeenCalledTimes(1);
    });
    expect(getPage).toHaveBeenCalledTimes(1);
  });

  it("renders a new bitmap when zoom changes on the same page", async () => {
    const renderPage = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
    const page = {
      getViewport: ({ scale }: { scale: number }) => ({
        width: 400 * scale,
        height: 600 * scale,
      }),
      render: renderPage,
      cleanup: vi.fn(),
    } as unknown as PDFPageProxy;
    const getPage = vi.fn(async () => page);
    const pdfDocument = { getPage } as unknown as PDFDocumentProxy;

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

    const { rerender } = render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[]}
        textBoxes={[]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={() => undefined}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={pdfDocument}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    await waitFor(() => {
      expect(renderPage).toHaveBeenCalledTimes(1);
    });

    rerender(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[]}
        textBoxes={[]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={() => undefined}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 460,
          height: 690,
          bottom: 690,
        }}
        pdfDocument={pdfDocument}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1.15}
      />,
    );

    await waitFor(() => {
      expect(renderPage).toHaveBeenCalledTimes(2);
    });
    expect(getPage).toHaveBeenCalledTimes(1);
  });

  it("renders contained text box toggle buttons for blocks", () => {
    const { container } = render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[
          {
            blockId: 1,
            pageIndex: 0,
            fractionRect: { x: 0.1, y: 0.1, width: 0.5, height: 0.5 },
            groupIdx: null,
          },
        ]}
        textBoxes={[
          {
            itemIndex: 1,
            pageIndex: 0,
            fractionRect: { x: 0.2, y: 0.2, width: 0.1, height: 0.1 },
          },
          {
            itemIndex: 2,
            pageIndex: 0,
            fractionRect: { x: 0.7, y: 0.7, width: 0.1, height: 0.1 },
          },
        ]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={() => undefined}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={null}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    expect(container.querySelectorAll(".pdf-page__textBox")).toHaveLength(1);
    expect(container.querySelectorAll(".pdf-block")).toHaveLength(1);
  });

  it("creates a full-page block when the page surface is double-clicked", () => {
    const onSurfaceDoubleClick = vi.fn();
    const { container } = render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[]}
        textBoxes={[]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={() => undefined}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onSurfaceDoubleClick={onSurfaceDoubleClick}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={null}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    const surface = container.querySelector(".pdf-page__surface");
    expect(surface).not.toBeNull();

    fireEvent.doubleClick(surface!);

    expect(onSurfaceDoubleClick).toHaveBeenCalledWith(0);
  });

  it("does not treat block double-clicks as page-surface double-clicks", () => {
    const onSurfaceDoubleClick = vi.fn();
    const { getByRole } = render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[
          {
            blockId: 1,
            pageIndex: 0,
            fractionRect: { x: 0.1, y: 0.1, width: 0.5, height: 0.5 },
            groupIdx: null,
          },
        ]}
        textBoxes={[]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={() => undefined}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onSurfaceDoubleClick={onSurfaceDoubleClick}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={null}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    fireEvent.doubleClick(getByRole("button", { name: "Block 1" }));

    expect(onSurfaceDoubleClick).not.toHaveBeenCalled();
  });

  it("only shows text box overlays after a block exists, not during drag preview alone", () => {
    const onBlockClick = vi.fn();
    const { getByRole, queryAllByTestId, rerender } = render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[]}
        textBoxes={[
          {
            itemIndex: 1,
            pageIndex: 0,
            fractionRect: { x: 0.2, y: 0.2, width: 0.1, height: 0.1 },
          },
        ]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={true}
        dragPreviewRect={{ x: 40, y: 60, width: 120, height: 90 }}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={onBlockClick}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={null}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    expect(queryAllByTestId("pdf-text-box-overlay")).toHaveLength(0);

    rerender(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[
          {
            blockId: 1,
            pageIndex: 0,
            fractionRect: { x: 0.1, y: 0.1, width: 0.5, height: 0.5 },
            groupIdx: null,
          },
        ]}
        textBoxes={[
          {
            itemIndex: 1,
            pageIndex: 0,
            fractionRect: { x: 0.2, y: 0.2, width: 0.1, height: 0.1 },
          },
        ]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={onBlockClick}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={null}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    expect(queryAllByTestId("pdf-text-box-overlay")).toHaveLength(1);
    fireEvent.click(getByRole("button", { name: "Block 1" }));
    expect(onBlockClick).toHaveBeenCalledTimes(1);
  });

  it("toggles disabled text boxes without triggering block clicks", () => {
    const onBlockClick = vi.fn();
    const onTextBoxToggle = vi.fn();

    const { getByRole } = render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[
          {
            blockId: 1,
            pageIndex: 0,
            fractionRect: { x: 0.1, y: 0.1, width: 0.5, height: 0.5 },
            groupIdx: null,
          },
        ]}
        textBoxes={[
          {
            itemIndex: 1,
            pageIndex: 0,
            fractionRect: { x: 0.2, y: 0.2, width: 0.1, height: 0.1 },
          },
        ]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[1]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={null}
        mergeSelectionBusy={false}
        onBlockClick={onBlockClick}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={() => undefined}
        onTextBoxToggle={onTextBoxToggle}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={null}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    const toggleButton = getByRole("button", { name: "Enable content item 1" });
    expect(toggleButton.className).toContain("pdf-page__textBox--disabled");

    fireEvent.click(toggleButton);

    expect(onTextBoxToggle).toHaveBeenCalledWith(1);
    expect(onBlockClick).not.toHaveBeenCalled();
  });

  it("renders a merge button for an active selection", () => {
    const onMergeSelection = vi.fn();

    const { getByRole } = render(
      <PdfPage
        assetName="asset-a"
        appMode="normal"
        blocks={[]}
        textBoxes={[]}
        busy={false}
        compressSelection={null}
        disabledContentItemIndexes={[]}
        dragPreviewActive={false}
        dragPreviewRect={null}
        hoveredBlockId={null}
        hoveredGroupIdx={null}
        mergeSelectionAction={{
          pageIndex: 0,
          rect: { x: 0.1, y: 0.1, width: 0.3, height: 0.2 },
          totalSelectedCount: 2,
        }}
        mergeSelectionBusy={false}
        onBlockClick={() => undefined}
        onBlockDelete={() => undefined}
        onBlockHoverEnter={() => undefined}
        onBlockHoverLeave={() => undefined}
        onMergeSelection={onMergeSelection}
        onTextBoxToggle={() => undefined}
        onSurfacePointerCancel={() => undefined}
        onSurfacePointerDown={() => undefined}
        onSurfacePointerMove={() => undefined}
        onSurfacePointerUp={() => undefined}
        pageLayout={{
          pageIndex: 0,
          top: 0,
          left: 0,
          width: 400,
          height: 600,
          bottom: 600,
        }}
        pdfDocument={null}
        renderQuality="final"
        selectionOrderByBlock={new Map()}
        zoom={1}
      />,
    );

    fireEvent.click(getByRole("button", { name: "Merge" }));

    expect(onMergeSelection).toHaveBeenCalledTimes(1);
  });
});
