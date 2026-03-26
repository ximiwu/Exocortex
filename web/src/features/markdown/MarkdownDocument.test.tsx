import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../app/api/ExocortexApiContext";
import type { ExocortexApi } from "../../app/api/exocortexApi";
import { useAppStore } from "../../app/store/appStore";
import type { AppStoreState } from "../../app/store/appStore";
import { MarkdownDocument } from "./MarkdownDocument";

const INITIAL_STORE_STATE = useAppStore.getState();

function resetStore(overrides: Partial<AppStoreState> = {}) {
  useAppStore.setState(
    {
      ...INITIAL_STORE_STATE,
      selectedAssetName: null,
      currentMarkdownPath: null,
      openTabs: [],
      ...overrides,
    },
    true,
  );
}

function createApi(): ExocortexApi {
  const api = {
    mode: "mock",
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
        tutorReasoningEffort: config.tutorReasoningEffort ?? "medium",
        tutorWithGlobalContext: config.tutorWithGlobalContext ?? true,
      })),
    },
    assets: {
      list: vi.fn(async () => []),
      getState: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      updateUiState: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      importAsset: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      deleteAsset: vi.fn(async () => undefined),
      revealAsset: vi.fn(async () => undefined),
    },
    markdown: {
      getTree: vi.fn(async () => []),
      getContent: vi.fn(async () => ({ path: "", title: "", markdown: "", html: "", bodyHtml: "", headHtml: "" })),
      getReference: vi.fn(async () => ""),
      renameNodeAlias: vi.fn(async () => ({ nodeId: "", path: null, title: "" })),
      reorderSiblings: vi.fn(async () => ({ parentId: null, orderedNodeIds: [] })),
    },
    pdf: {
      buildFileUrl: vi.fn(() => ""),
      getMetadata: vi.fn(async () => ({
        pageCount: 0,
        pageSizes: [],
        defaultDpi: 130,
        minDpi: 72,
        maxDpi: 1200,
      })),
      getPageTextBoxes: vi.fn(async (_assetName, pageIndex) => ({
        pageIndex,
        items: [],
      })),
      searchContent: vi.fn(async (_assetName, query) => ({ query, matches: [] })),
      createBlock: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      deleteBlock: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      deleteGroup: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      updateDisabledContentItems: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      updateSelection: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      previewMergeMarkdown: vi.fn(async () => ({ markdown: "", warning: null })),
      mergeGroup: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      updateUiState: vi.fn(async () => {
        throw new Error("not implemented");
      }),
    },
    tasks: {
      list: vi.fn(async () => []),
      get: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      subscribe: vi.fn(() => () => undefined),
    },
    workflows: {
      createTutorSession: vi.fn(async () => ({ tutorIdx: 1, markdownPath: "group_data/1/tutor_data/1/focus.md" })),
      submitGroupDive: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitFlashcard: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitAskTutor: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitReTutor: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitIntegrate: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitBugFinder: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitStudentNote: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitFixLatex: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitCompressPreview: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitCompressExecute: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      deleteQuestion: vi.fn(async () => undefined),
      deleteTutorSession: vi.fn(async () => undefined),
    },
  };
  return api as unknown as ExocortexApi;
}

describe("MarkdownDocument", () => {
  beforeEach(() => {
    resetStore();
    vi.stubGlobal("requestAnimationFrame", ((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    }) as typeof requestAnimationFrame);
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
  });

  afterEach(() => {
    cleanup();
    useAppStore.setState(INITIAL_STORE_STATE, true);
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("does not overwrite saved scroll progress during the loading placeholder state", async () => {
    const assetName = "asset-a";
    const path = "group_data/1/img_explainer_data/enhanced.md";

    resetStore({
      markdownScrollFractionsByAsset: {
        [assetName]: {
          [path]: 0.5,
        },
      },
    });

    const view = render(
      <ExocortexApiProvider api={createApi()}>
        <MarkdownDocument
          assetName={assetName}
          path={path}
          html=""
          loading
          error={null}
          renderVersion={1}
        />
      </ExocortexApiProvider>,
    );

    const scrollElement = view.container.querySelector(".workspace__documentScroll") as HTMLDivElement;
    expect(scrollElement).not.toBeNull();

    Object.defineProperty(scrollElement, "scrollHeight", {
      configurable: true,
      value: 100,
    });
    Object.defineProperty(scrollElement, "clientHeight", {
      configurable: true,
      value: 100,
    });
    scrollElement.scrollTop = 0;

    fireEvent.scroll(scrollElement);
    expect(useAppStore.getState().markdownScrollFractionsByAsset[assetName]?.[path]).toBe(0.5);

    Object.defineProperty(scrollElement, "scrollHeight", {
      configurable: true,
      value: 1000,
    });
    Object.defineProperty(scrollElement, "clientHeight", {
      configurable: true,
      value: 100,
    });

    view.rerender(
      <ExocortexApiProvider api={createApi()}>
        <MarkdownDocument
          assetName={assetName}
          path={path}
          html="<p>Loaded</p>"
          loading={false}
          error={null}
          renderVersion={1}
        />
      </ExocortexApiProvider>,
    );

    await waitFor(() => {
      expect(scrollElement.scrollTop).toBe(450);
    });
    expect(useAppStore.getState().markdownScrollFractionsByAsset[assetName]?.[path]).toBe(0.5);
  });
});
