import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../app/api/ExocortexApiContext";
import { queryKeys, type ExocortexApi } from "../../app/api/exocortexApi";
import { useAppStore } from "../../app/store/appStore";
import type { AppStoreState } from "../../app/store/appStore.types";
import type { MarkdownTab } from "../../app/types";
import { usePdfDocument } from "./usePdfDocument";
import type { PdfAssetState, PdfMetadata, PdfUiState } from "./types";

const ASSET_STATE: PdfAssetState = {
  asset: {
    name: "asset-a",
    pageCount: 3,
    pdfPath: "asset-a/raw.pdf",
  },
  references: [],
  blocks: [],
  mergeOrder: [],
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
  pageCount: 3,
  pageSizes: [
    { width: 100, height: 200 },
    { width: 100, height: 200 },
    { width: 100, height: 200 },
  ],
  defaultDpi: 130,
  minDpi: 72,
  maxDpi: 300,
};

const INITIAL_STORE_STATE = useAppStore.getState();

type PdfDocumentResult = ReturnType<typeof usePdfDocument>;

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
  return {
    promise,
    resolve,
    reject,
  };
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function buildAssetState(uiState: Partial<PdfUiState>): PdfAssetState {
  return {
    ...clone(ASSET_STATE),
    uiState: {
      ...clone(ASSET_STATE.uiState),
      ...uiState,
    },
  };
}

function resetStore(overrides: Partial<AppStoreState> = {}) {
  useAppStore.setState(
    {
      ...INITIAL_STORE_STATE,
      selectedAssetName: "asset-a",
      sidebarCollapsed: false,
      sidebarWidthRatio: 0.2,
      rightRailWidthRatio: 0.25,
      currentMarkdownPath: null,
      openTabs: [],
      sidebarCollapsedNodeIdsByAsset: {},
      markdownScrollFractionsByAsset: {},
      ...overrides,
    },
    true,
  );
}

function createApiMock(
  updatePdfUiState: (assetName: string, uiState: PdfAssetState["uiState"]) => Promise<PdfAssetState>,
  previewMergeMarkdown: (assetName: string, blockIds: number[]) => Promise<{ markdown: string }> = vi.fn(
    async () => ({ markdown: "" }),
  ),
): ExocortexApi {
  return {
    mode: "live",
    capabilities: {
      deleteQuestion: true,
      deleteTutorSession: true,
    },
    system: {
      getConfig: vi.fn(async () => ({
        themeMode: "light" as const,
        sidebarTextLineClamp: 1,
        sidebarFontSizePx: 14,
        tutorReasoningEffort: "medium" as const,
        tutorWithGlobalContext: true,
      })),
      updateConfig: vi.fn(async (config) => ({
        themeMode: "light" as const,
        sidebarTextLineClamp: 1,
        sidebarFontSizePx: 14,
        tutorReasoningEffort: "medium" as const,
        tutorWithGlobalContext: true,
        ...config,
      })),
    },
    assets: {
      list: vi.fn(async () => []),
      getState: vi.fn(async () => clone(ASSET_STATE)),
      updateUiState: vi.fn(async (_assetName, uiState) => buildAssetState(uiState)),
      importAsset: vi.fn(),
      deleteAsset: vi.fn(),
      revealAsset: vi.fn(),
    },
    markdown: {
      getTree: vi.fn(async () => []),
      getContent: vi.fn(),
      getReference: vi.fn(),
      renameNodeAlias: vi.fn(),
      reorderSiblings: vi.fn(),
    },
    pdf: {
      buildFileUrl: vi.fn(() => "/api/assets/asset-a/pdf/file"),
      getMetadata: vi.fn(async () => clone(METADATA)),
      getPageTextBoxes: vi.fn(async (_assetName, pageIndex) => ({
        pageIndex,
        items: [],
      })),
      createBlock: vi.fn(),
      deleteBlock: vi.fn(),
      deleteGroup: vi.fn(),
      updateSelection: vi.fn(),
      previewMergeMarkdown: vi.fn(previewMergeMarkdown),
      mergeGroup: vi.fn(),
      updateUiState: vi.fn(updatePdfUiState),
    },
    tasks: {
      list: vi.fn(async () => []),
      get: vi.fn(),
      subscribe: vi.fn(() => () => undefined),
    },
    workflows: {
      createTutorSession: vi.fn(),
      submitGroupDive: vi.fn(),
      submitAskTutor: vi.fn(),
      submitReTutor: vi.fn(),
      submitIntegrate: vi.fn(),
      submitBugFinder: vi.fn(),
      submitStudentNote: vi.fn(),
      submitFixLatex: vi.fn(),
      submitCompressPreview: vi.fn(),
      submitCompressExecute: vi.fn(),
      deleteQuestion: vi.fn(),
      deleteTutorSession: vi.fn(),
    },
  } as ExocortexApi;
}

function PdfDocumentHarness({
  assetName,
  onChange,
}: {
  assetName: string | null;
  onChange: (value: PdfDocumentResult) => void;
}) {
  const value = usePdfDocument(assetName);

  useEffect(() => {
    onChange(value);
  }, [onChange, value]);

  return null;
}

describe("usePdfDocument", () => {
  beforeEach(() => {
    resetStore();
  });

  afterEach(() => {
    useAppStore.setState(INITIAL_STORE_STATE, true);
    vi.restoreAllMocks();
  });

  it("ignores stale PDF ui-state responses that resolve after a newer write", async () => {
    const firstResponse = createDeferred<PdfAssetState>();
    const secondResponse = createDeferred<PdfAssetState>();
    const updatePdfUiState = vi
      .fn<(assetName: string, uiState: PdfAssetState["uiState"]) => Promise<PdfAssetState>>()
      .mockImplementationOnce(async () => firstResponse.promise)
      .mockImplementationOnce(async () => secondResponse.promise);
    const api = createApiMock(updatePdfUiState);
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    let latestValue: PdfDocumentResult | null = null;

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <PdfDocumentHarness
            assetName="asset-a"
            onChange={(value) => {
              latestValue = value;
            }}
          />
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(latestValue?.assetState).not.toBeNull();
      expect(latestValue?.metadata).not.toBeNull();
    });

    act(() => {
      void latestValue?.patchUiState({
        currentPage: 2,
        zoom: 1.25,
        pdfScrollFraction: 0.2,
        pdfScrollLeftFraction: 0,
      });
      void latestValue?.patchUiState({
        currentPage: 3,
        zoom: 1.5,
        pdfScrollFraction: 0.4,
        pdfScrollLeftFraction: 0.1,
      });
    });

    await act(async () => {
      secondResponse.resolve(
        buildAssetState({
          currentPage: 3,
          zoom: 1.5,
          pdfScrollFraction: 0.4,
          pdfScrollLeftFraction: 0.1,
        }),
      );
      await secondResponse.promise;
    });

    await waitFor(() => {
      const cachedState = queryClient.getQueryData<PdfAssetState>(queryKeys.assetState("asset-a"));
      expect(cachedState?.uiState.currentPage).toBe(3);
      expect(cachedState?.uiState.zoom).toBe(1.5);
      expect(cachedState?.uiState.pdfScrollFraction).toBe(0.4);
      expect(cachedState?.uiState.pdfScrollLeftFraction).toBe(0.1);
    });

    await act(async () => {
      firstResponse.resolve(
        buildAssetState({
          currentPage: 2,
          zoom: 1.25,
          pdfScrollFraction: 0.2,
          pdfScrollLeftFraction: 0,
        }),
      );
      await firstResponse.promise;
    });

    await waitFor(() => {
      const cachedState = queryClient.getQueryData<PdfAssetState>(queryKeys.assetState("asset-a"));
      expect(cachedState?.uiState.currentPage).toBe(3);
      expect(cachedState?.uiState.zoom).toBe(1.5);
      expect(cachedState?.uiState.pdfScrollFraction).toBe(0.4);
      expect(cachedState?.uiState.pdfScrollLeftFraction).toBe(0.1);
    });
  });

  it("writes the current local shell layout into PDF ui-state requests and cache updates", async () => {
    const currentTab: MarkdownTab = {
      assetName: "asset-a",
      path: "group_data/1/img_explainer_data/enhanced.md",
      title: "enhanced.md",
      kind: "markdown",
    };
    resetStore({
      selectedAssetName: "asset-a",
      currentMarkdownPath: currentTab.path,
      openTabs: [currentTab],
      sidebarCollapsed: true,
      sidebarWidthRatio: 0.42,
      rightRailWidthRatio: 0.33,
      sidebarCollapsedNodeIdsByAsset: {
        "asset-a": ["group:1"],
      },
      markdownScrollFractionsByAsset: {
        "asset-a": {
          [currentTab.path]: 0.61,
        },
      },
    });

    const response = createDeferred<PdfAssetState>();
    const updatePdfUiState = vi.fn(async () => response.promise);
    const api = createApiMock(updatePdfUiState);
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    let latestValue: PdfDocumentResult | null = null;

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <PdfDocumentHarness
            assetName="asset-a"
            onChange={(value) => {
              latestValue = value;
            }}
          />
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(latestValue?.assetState).not.toBeNull();
      expect(latestValue?.metadata).not.toBeNull();
    });

    act(() => {
      void latestValue?.patchUiState({
        currentPage: 2,
        zoom: 1.1,
        pdfScrollFraction: 0.25,
        pdfScrollLeftFraction: 0,
      });
    });

    await waitFor(() => {
      expect(updatePdfUiState).toHaveBeenCalledWith(
        "asset-a",
        expect.objectContaining({
          currentMarkdownPath: currentTab.path,
          openMarkdownPaths: [currentTab.path],
          sidebarCollapsed: true,
          sidebarCollapsedNodeIds: ["group:1"],
          markdownScrollFractions: {
            [currentTab.path]: 0.61,
          },
          sidebarWidthRatio: 0.42,
          rightRailWidthRatio: 0.33,
        }),
      );
    });

    await act(async () => {
      response.resolve(
        buildAssetState({
          currentPage: 2,
          zoom: 1.1,
          pdfScrollFraction: 0.25,
          pdfScrollLeftFraction: 0,
          currentMarkdownPath: null,
          openMarkdownPaths: [],
          sidebarCollapsed: false,
          sidebarCollapsedNodeIds: [],
          markdownScrollFractions: {},
          sidebarWidthRatio: 0.2,
          rightRailWidthRatio: 0.25,
        }),
      );
      await response.promise;
    });

    await waitFor(() => {
      const cachedState = queryClient.getQueryData<PdfAssetState>(queryKeys.assetState("asset-a"));
      expect(cachedState?.uiState.currentMarkdownPath).toBe(currentTab.path);
      expect(cachedState?.uiState.openMarkdownPaths).toEqual([currentTab.path]);
      expect(cachedState?.uiState.sidebarCollapsed).toBe(true);
      expect(cachedState?.uiState.sidebarCollapsedNodeIds).toEqual(["group:1"]);
      expect(cachedState?.uiState.markdownScrollFractions).toEqual({
        [currentTab.path]: 0.61,
      });
      expect(cachedState?.uiState.sidebarWidthRatio).toBe(0.42);
      expect(cachedState?.uiState.rightRailWidthRatio).toBe(0.33);
    });
  });

  it("exposes markdown preview through the PDF api wrapper", async () => {
    const previewMergeMarkdown = vi.fn(async () => ({ markdown: "## Prefill" }));
    const api = createApiMock(vi.fn(async (_assetName, uiState) => buildAssetState(uiState)), previewMergeMarkdown);
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    let latestValue: PdfDocumentResult | null = null;

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <PdfDocumentHarness
            assetName="asset-a"
            onChange={(value) => {
              latestValue = value;
            }}
          />
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(latestValue?.assetState).not.toBeNull();
    });

    await act(async () => {
      await expect(latestValue?.previewMergeMarkdown([4, 7])).resolves.toEqual({
        markdown: "## Prefill",
      });
    });

    expect(previewMergeMarkdown).toHaveBeenCalledWith("asset-a", [4, 7]);
  });
});
