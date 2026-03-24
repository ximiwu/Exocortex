import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PdfNavigationRequest } from "../../../app/store/appStore.types";
import type { PdfAssetState, PdfMetadata, PdfUiState } from "../types";
import { usePdfPaneInteractions } from "./usePdfPaneInteractions";

const ASSET_STATE: PdfAssetState = {
  asset: {
    name: "asset-a",
    pageCount: 12,
    pdfPath: "asset-a.pdf",
  },
  references: [],
  blocks: [],
  mergeOrder: [],
  disabledContentItemIndexes: [],
  nextBlockId: 1,
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
  pageCount: 12,
  pageSizes: Array.from({ length: 12 }, () => ({ width: 100, height: 200 })),
  defaultDpi: 130,
  minDpi: 72,
  maxDpi: 300,
};

interface HarnessProps {
  attachViewport?: boolean;
  navigationRequest: PdfNavigationRequest | null;
  onNavigationHandled: (request: PdfNavigationRequest) => void;
  onUiStateChange: (patch: Partial<PdfUiState>) => void;
  scrollToSpy: ReturnType<typeof vi.fn>;
}

function PdfInteractionsHarness({
  attachViewport = true,
  navigationRequest,
  onNavigationHandled,
  onUiStateChange,
  scrollToSpy,
}: HarnessProps) {
  const interactions = usePdfPaneInteractions({
    assetName: "asset-a",
    assetState: ASSET_STATE,
    metadata: METADATA,
    appMode: "normal",
    initialCompressSelection: null,
    onUiStateChange,
    navigationRequest,
    onNavigationHandled,
  });

  return (
    <>
      <output data-testid="current-page">{interactions.currentPage}</output>
      <output data-testid="preheat-pages">{interactions.preheatPageIndexes.join(",")}</output>
      {attachViewport ? (
        <div
          data-testid="viewport"
          ref={(element) => {
            if (!element) {
              interactions.viewportRef(null);
              return;
            }

            Object.defineProperty(element, "clientHeight", {
              configurable: true,
              value: 150,
            });
            Object.defineProperty(element, "clientWidth", {
              configurable: true,
              value: 80,
            });
            Object.defineProperty(element, "scrollTo", {
              configurable: true,
              value: ({ top = 0, left = 0 }: ScrollToOptions) => {
                if (typeof top === "number") {
                  element.scrollTop = top;
                }
                if (typeof left === "number") {
                  element.scrollLeft = left;
                }
                scrollToSpy({ top, left });
              },
            });
            interactions.viewportRef(element);
          }}
          onScroll={interactions.handleScroll}
        />
      ) : null}
    </>
  );
}

describe("usePdfPaneInteractions external navigation", () => {
  beforeEach(() => {
    vi.stubGlobal("requestAnimationFrame", ((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    }) as typeof requestAnimationFrame);
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("jumps to the requested page and writes back the matching ui state", async () => {
    const onNavigationHandled = vi.fn();
    const onUiStateChange = vi.fn();
    const scrollToSpy = vi.fn();
    const navigationRequest: PdfNavigationRequest = {
      assetName: "asset-a",
      page: 3,
      nonce: 99,
    };

    render(
      <PdfInteractionsHarness
        navigationRequest={navigationRequest}
        onNavigationHandled={onNavigationHandled}
        onUiStateChange={onUiStateChange}
        scrollToSpy={scrollToSpy}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("current-page")).toHaveTextContent("3");
    });

    await waitFor(() => {
      expect(onNavigationHandled).toHaveBeenCalledWith(navigationRequest);
    });

    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 456,
      left: 0,
    });

    const latestUiState = onUiStateChange.mock.calls.at(-1)?.[0];
    expect(latestUiState).toEqual(
      expect.objectContaining({
        currentPage: 3,
        zoom: 1,
        pdfScrollLeftFraction: 0,
      }),
    );
    expect(latestUiState.pdfScrollFraction).toBeCloseTo(456 / 2558, 5);
  });

  it("retries a pending navigation request once the viewport becomes available", async () => {
    const onNavigationHandled = vi.fn();
    const onUiStateChange = vi.fn();
    const scrollToSpy = vi.fn();
    const navigationRequest: PdfNavigationRequest = {
      assetName: "asset-a",
      page: 3,
      nonce: 123,
    };

    const { rerender } = render(
      <PdfInteractionsHarness
        attachViewport={false}
        navigationRequest={navigationRequest}
        onNavigationHandled={onNavigationHandled}
        onUiStateChange={onUiStateChange}
        scrollToSpy={scrollToSpy}
      />,
    );

    expect(screen.getByTestId("current-page")).toHaveTextContent("1");
    expect(onNavigationHandled).not.toHaveBeenCalled();
    expect(scrollToSpy).not.toHaveBeenCalled();

    rerender(
      <PdfInteractionsHarness
        attachViewport
        navigationRequest={navigationRequest}
        onNavigationHandled={onNavigationHandled}
        onUiStateChange={onUiStateChange}
        scrollToSpy={scrollToSpy}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("current-page")).toHaveTextContent("3");
    });

    await waitFor(() => {
      expect(onNavigationHandled).toHaveBeenCalledWith(navigationRequest);
    });

    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 456,
      left: 0,
    });
  });
});

interface DoubleClickHarnessProps {
  appMode: "normal" | "compress";
  onCreateBlock: (pageIndex: number, rect: { x: number; y: number; width: number; height: number }) => void;
}

function PdfDoubleClickHarness({ appMode, onCreateBlock }: DoubleClickHarnessProps) {
  const interactions = usePdfPaneInteractions({
    assetName: "asset-a",
    assetState: ASSET_STATE,
    metadata: METADATA,
    appMode,
    initialCompressSelection: null,
    onCreateBlock,
  });

  return (
    <button
      onClick={() => {
        interactions.handleSurfaceDoubleClick(4);
      }}
      type="button"
    >
      Double click page
    </button>
  );
}

describe("usePdfPaneInteractions full-page block creation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a full-page block in normal mode", () => {
    const onCreateBlock = vi.fn();

    render(<PdfDoubleClickHarness appMode="normal" onCreateBlock={onCreateBlock} />);

    fireEvent.click(screen.getByRole("button", { name: "Double click page" }));

    expect(onCreateBlock).toHaveBeenCalledWith(4, {
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });
  });

  it("ignores page-surface double-clicks in compress mode", () => {
    const onCreateBlock = vi.fn();

    render(<PdfDoubleClickHarness appMode="compress" onCreateBlock={onCreateBlock} />);

    fireEvent.click(screen.getByRole("button", { name: "Double click page" }));

    expect(onCreateBlock).not.toHaveBeenCalled();
  });
});
