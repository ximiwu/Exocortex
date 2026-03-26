import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../../app/api/ExocortexApiContext";
import type { PdfPageTextBoxes } from "../../../app/api/types";
import type { ExocortexApi } from "../../../app/api/exocortexApi";
import { usePdfPageTextBoxes } from "./usePdfPageTextBoxes";

function createApi(
  getPageTextBoxes: (assetName: string, pageIndex: number) => Promise<PdfPageTextBoxes>,
): ExocortexApi {
  return {
    mode: "mock",
    capabilities: {
      deleteQuestion: true,
      deleteTutorSession: true,
    },
    system: {
      getConfig: vi.fn(),
      updateConfig: vi.fn(),
    },
    assets: {
      list: vi.fn(),
      getState: vi.fn(),
      updateUiState: vi.fn(),
      importAsset: vi.fn(),
      deleteAsset: vi.fn(),
      revealAsset: vi.fn(),
    },
    markdown: {
      getTree: vi.fn(),
      getContent: vi.fn(),
      getReference: vi.fn(),
      renameNodeAlias: vi.fn(),
      reorderSiblings: vi.fn(),
    },
    pdf: {
      buildFileUrl: vi.fn(() => ""),
      getMetadata: vi.fn(),
      getPageTextBoxes: vi.fn(getPageTextBoxes),
      searchContent: vi.fn(async (_assetName, query) => ({ query, matches: [] })),
      createBlock: vi.fn(),
      deleteBlock: vi.fn(),
      deleteGroup: vi.fn(),
      updateDisabledContentItems: vi.fn(),
      updateSelection: vi.fn(),
      previewMergeMarkdown: vi.fn(async () => ({ markdown: "" })),
      mergeGroup: vi.fn(),
      updateUiState: vi.fn(),
    },
    tasks: {
      list: vi.fn(),
      get: vi.fn(),
      subscribe: vi.fn(() => () => undefined),
    },
    workflows: {
      createTutorSession: vi.fn(),
      submitGroupDive: vi.fn(),
      submitFlashcard: vi.fn(),
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
  };
}

function HookHarness({
  assetName,
  visiblePageIndexes,
  preheatPageIndexes,
  onChange,
}: {
  assetName: string | null;
  visiblePageIndexes: number[];
  preheatPageIndexes: number[];
  onChange: (value: ReturnType<typeof usePdfPageTextBoxes>) => void;
}) {
  const value = usePdfPageTextBoxes({
    assetName,
    enabled: Boolean(assetName),
    visiblePageIndexes,
    preheatPageIndexes,
  });

  useEffect(() => {
    onChange(value);
  }, [onChange, value]);

  return null;
}

describe("usePdfPageTextBoxes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads visible pages and prefetches preheat pages", async () => {
    const getPageTextBoxes = vi.fn(async (_assetName: string, pageIndex: number) => ({
      pageIndex,
      items: [
        {
          itemIndex: pageIndex + 1,
          pageIndex,
          fractionRect: {
            x: 0.1,
            y: 0.1,
            width: 0.2,
            height: 0.1,
          },
        },
      ],
    }));
    const api = createApi(getPageTextBoxes);
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    let latestValue: ReturnType<typeof usePdfPageTextBoxes> | null = null;

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <HookHarness
            assetName="asset-a"
            onChange={(value) => {
              latestValue = value;
            }}
            preheatPageIndexes={[3]}
            visiblePageIndexes={[1, 2]}
          />
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 1);
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 2);
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 3);
    });

    await waitFor(() => {
      expect(latestValue?.textBoxesByPage.get(1)?.[0]?.pageIndex).toBe(1);
      expect(latestValue?.textBoxesByPage.get(2)?.[0]?.pageIndex).toBe(2);
    });
  });

  it("does not prefetch a page already visible", async () => {
    const getPageTextBoxes = vi.fn(async (_assetName: string, pageIndex: number) => ({
      pageIndex,
      items: [],
    }));
    const api = createApi(getPageTextBoxes);
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <HookHarness
            assetName="asset-a"
            onChange={() => undefined}
            preheatPageIndexes={[1, 2]}
            visiblePageIndexes={[1]}
          />
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 1);
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 2);
    });

    const callsForPageOne = getPageTextBoxes.mock.calls.filter(
      (entry) => entry[0] === "asset-a" && entry[1] === 1,
    );
    expect(callsForPageOne).toHaveLength(1);
  });

  it("fetches newly visible pages when the viewport changes", async () => {
    const getPageTextBoxes = vi.fn(async (_assetName: string, pageIndex: number) => ({
      pageIndex,
      items: [
        {
          itemIndex: pageIndex + 1,
          pageIndex,
          fractionRect: { x: 0.1, y: 0.1, width: 0.2, height: 0.1 },
        },
      ],
    }));
    const api = createApi(getPageTextBoxes);
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    let latestValue: ReturnType<typeof usePdfPageTextBoxes> | null = null;

    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <HookHarness
            assetName="asset-a"
            onChange={(value) => {
              latestValue = value;
            }}
            preheatPageIndexes={[1]}
            visiblePageIndexes={[0]}
          />
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 0);
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 1);
    });

    rerender(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <HookHarness
            assetName="asset-a"
            onChange={(value) => {
              latestValue = value;
            }}
            preheatPageIndexes={[3]}
            visiblePageIndexes={[1, 2]}
          />
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 2);
      expect(getPageTextBoxes).toHaveBeenCalledWith("asset-a", 3);
      expect(latestValue?.textBoxesByPage.get(1)?.[0]?.pageIndex).toBe(1);
      expect(latestValue?.textBoxesByPage.get(2)?.[0]?.pageIndex).toBe(2);
    });

    const callsForPageOne = getPageTextBoxes.mock.calls.filter(
      (entry) => entry[0] === "asset-a" && entry[1] === 1,
    );
    expect(callsForPageOne).toHaveLength(1);
  });
});
