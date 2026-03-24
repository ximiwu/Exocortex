import { act, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PdfPane } from "./PdfPane";
import { usePdfPageTextBoxes } from "./hooks/usePdfPageTextBoxes";
import { usePdfPaneInteractions } from "./hooks/usePdfPaneInteractions";
import { usePdfJsDocument } from "./hooks/usePdfJsDocument";
import type { PdfAssetState, PdfMetadata } from "./types";

vi.mock("./hooks/usePdfPaneInteractions", () => ({
  usePdfPaneInteractions: vi.fn(),
}));

vi.mock("./hooks/usePdfPageTextBoxes", () => ({
  usePdfPageTextBoxes: vi.fn(),
}));

vi.mock("./hooks/usePdfJsDocument", () => ({
  usePdfJsDocument: vi.fn(),
}));

vi.mock("./components/PdfPaneViewport", () => ({
  PdfPaneViewport: (props: {
    mergeSelectionBusy: boolean;
    onMergeSelection: () => void;
  }) => (
    <div>
      <button disabled={props.mergeSelectionBusy} onClick={props.onMergeSelection} type="button">
        Merge
      </button>
    </div>
  ),
}));

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const ASSET_STATE: PdfAssetState = {
  asset: {
    name: "asset-a",
    pageCount: 2,
    pdfPath: "asset-a/raw.pdf",
  },
  references: [],
  blocks: [],
  mergeOrder: [1, 2],
  disabledContentItemIndexes: [],
  nextBlockId: 3,
  groups: [],
  uiState: {
    currentPage: 1,
    zoom: 1,
    pdfScrollFraction: 0,
    pdfScrollLeftFraction: 0,
    currentMarkdownPath: null,
    openMarkdownPaths: [],
    sidebarCollapsed: false,
    sidebarCollapsedNodeIds: [],
    markdownScrollFractions: {},
    sidebarWidthRatio: 0.2,
    rightRailWidthRatio: 0.25,
  },
};

const METADATA: PdfMetadata = {
  pageCount: 2,
  pageSizes: [
    { width: 100, height: 200 },
    { width: 100, height: 200 },
  ],
  defaultDpi: 130,
  minDpi: 72,
  maxDpi: 300,
};

function createInteractions() {
  return {
    currentPage: 1,
    currentPageIndex: 0,
    handlePageInputChange: vi.fn(),
    applyZoom: vi.fn(),
    zoom: 1,
    pageCount: 2,
    blocksByPage: new Map(),
    canvasHeight: 400,
    canvasWidth: 200,
    compressSelection: null,
    dragSelection: {
      activePageIndex: null,
      previewRect: null,
      isDragging: false,
      beginDrag: vi.fn(),
      updateDrag: vi.fn(),
      endDrag: vi.fn(),
      cancelDrag: vi.fn(),
    },
    hoverState: {
      hoveredBlockId: null,
      hoveredGroupIdx: null,
    },
    isScrolling: false,
    isRightPanning: false,
    layouts: [],
    mergeSelectionAction: {
      pageIndex: 0,
      rect: { x: 0.1, y: 0.1, width: 0.2, height: 0.2 },
      totalSelectedCount: 2,
    },
    beginPan: vi.fn(),
    handleBlockClick: vi.fn(),
    handleBlockDelete: vi.fn(),
    handleBlockHoverEnter: vi.fn(),
    handleBlockHoverLeave: vi.fn(),
    cancelPan: vi.fn(),
    endPan: vi.fn(),
    handleScroll: vi.fn(),
    handleSurfaceDoubleClick: vi.fn(),
    updatePan: vi.fn(),
    pageSizes: METADATA.pageSizes,
    preheatPageIndexes: [],
    selectionOrderByBlock: new Map<number, number>(),
    suppressNextContextMenuRef: { current: false },
    viewportRef: vi.fn(),
    visiblePageIndexes: [0],
  };
}

describe("PdfPane", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("opens merge with generated markdown, allows editing, and confirms", async () => {
    vi.mocked(usePdfPaneInteractions).mockReturnValue(createInteractions());
    vi.mocked(usePdfPageTextBoxes).mockReturnValue({
      textBoxesByPage: new Map(),
      loading: false,
      error: null,
    });
    vi.mocked(usePdfJsDocument).mockReturnValue({
      pdfDocument: null,
      loading: false,
      error: null,
    });

    const onPreviewMergeMarkdown = vi.fn(async () => ({ markdown: "## Suggested" }));
    const onMergeSelection = vi.fn(async () => undefined);

    const { getByRole } = render(
      <PdfPane
        assetName="asset-a"
        assetState={ASSET_STATE}
        metadata={METADATA}
        onMergeSelection={onMergeSelection}
        onPreviewMergeMarkdown={onPreviewMergeMarkdown}
      />,
    );

    fireEvent.click(getByRole("button", { name: "Merge" }));

    const textarea = getByRole("textbox", { name: "Markdown" }) as HTMLTextAreaElement;
    await waitFor(() => {
      expect(textarea.value).toBe("## Suggested");
    });

    fireEvent.change(textarea, { target: { value: "# Edited" } });
    fireEvent.click(getByRole("button", { name: "Confirm" }));

    await waitFor(() => {
      expect(onMergeSelection).toHaveBeenCalledWith([1, 2], {
        markdownContent: "# Edited",
      });
    });
  });

  it("opens auto merge, disables controls while loading, fills the textarea, and confirms", async () => {
    vi.mocked(usePdfPaneInteractions).mockReturnValue(createInteractions());
    vi.mocked(usePdfPageTextBoxes).mockReturnValue({
      textBoxesByPage: new Map(),
      loading: false,
      error: null,
    });
    vi.mocked(usePdfJsDocument).mockReturnValue({
      pdfDocument: null,
      loading: false,
      error: null,
    });

    const preview = createDeferred<{ markdown: string }>();
    const onPreviewMergeMarkdown = vi.fn(() => preview.promise);
    const onMergeSelection = vi.fn(async () => undefined);

    const { getByRole } = render(
      <PdfPane
        assetName="asset-a"
        assetState={ASSET_STATE}
        metadata={METADATA}
        onMergeSelection={onMergeSelection}
        onPreviewMergeMarkdown={onPreviewMergeMarkdown}
      />,
    );

    fireEvent.click(getByRole("button", { name: "Merge" }));

    expect(getByRole("button", { name: "Merge" })).toBeDisabled();
    expect(getByRole("button", { name: "Confirm" })).toBeDisabled();

    await act(async () => {
      preview.resolve({ markdown: "## Auto filled" });
      await preview.promise;
    });

    const textarea = getByRole("textbox", { name: "Markdown" }) as HTMLTextAreaElement;
    await waitFor(() => {
      expect(textarea.value).toBe("## Auto filled");
    });

    fireEvent.click(getByRole("button", { name: "Confirm" }));

    await waitFor(() => {
      expect(onMergeSelection).toHaveBeenCalledWith([1, 2], {
        markdownContent: "## Auto filled",
      });
    });
  });

  it("alerts when preview generation falls back to img_path for images", async () => {
    vi.mocked(usePdfPaneInteractions).mockReturnValue(createInteractions());
    vi.mocked(usePdfPageTextBoxes).mockReturnValue({
      textBoxesByPage: new Map(),
      loading: false,
      error: null,
    });
    vi.mocked(usePdfJsDocument).mockReturnValue({
      pdfDocument: null,
      loading: false,
      error: null,
    });

    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const onPreviewMergeMarkdown = vi.fn(async () => ({
      markdown: "## Suggested",
      warning: "Image item 4 is missing image_explaination. The markdown preview fell back to img_path.",
    }));

    const { getByRole } = render(
      <PdfPane
        assetName="asset-a"
        assetState={ASSET_STATE}
        metadata={METADATA}
        onMergeSelection={vi.fn(async () => undefined)}
        onPreviewMergeMarkdown={onPreviewMergeMarkdown}
      />,
    );

    fireEvent.click(getByRole("button", { name: "Merge" }));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith(
        "Image item 4 is missing image_explaination. The markdown preview fell back to img_path.",
      );
    });
  });

  it("keeps the dialog open and shows an inline error when merge prefill fails", async () => {
    vi.mocked(usePdfPaneInteractions).mockReturnValue(createInteractions());
    vi.mocked(usePdfPageTextBoxes).mockReturnValue({
      textBoxesByPage: new Map(),
      loading: false,
      error: null,
    });
    vi.mocked(usePdfJsDocument).mockReturnValue({
      pdfDocument: null,
      loading: false,
      error: null,
    });

    const onPreviewMergeMarkdown = vi.fn(async () => {
      throw new Error("Preview failed");
    });

    const { findByText, getByRole } = render(
      <PdfPane
        assetName="asset-a"
        assetState={ASSET_STATE}
        metadata={METADATA}
        onMergeSelection={vi.fn(async () => undefined)}
        onPreviewMergeMarkdown={onPreviewMergeMarkdown}
      />,
    );

    fireEvent.click(getByRole("button", { name: "Merge" }));

    expect(await findByText("Preview failed")).toBeTruthy();
    expect(getByRole("textbox", { name: "Markdown" })).toBeInTheDocument();
  });
});
