import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../../app/api/ExocortexApiContext";
import type { ExocortexApi } from "../../../app/api/exocortexApi";
import type { ImportAssetInput } from "../../../app/api/types";
import { useAppStore } from "../../../app/store/appStore";
import type { AppStoreState } from "../../../app/store/appStore.types";
import { ToastProvider } from "../../tasks/ToastProvider";
import { useWorkflowCommandController } from "./useWorkflowCommandController";

const DEFAULT_SYSTEM_CONFIG = {
  themeMode: "light" as const,
  sidebarTextLineClamp: 1,
  sidebarFontSizePx: 14,
  tutorReasoningEffort: "medium" as const,
  tutorWithGlobalContext: true,
};

const SUBMITTED_TASK = {
  id: "task-1",
  kind: "ask_tutor",
  status: "queued" as const,
  title: "Ask Tutor",
  assetName: "asset-a",
  createdAt: "2026-03-24T12:00:00Z",
  updatedAt: "2026-03-24T12:00:00Z",
};

const INITIAL_STORE_STATE = useAppStore.getState();

let trackSubmittedTaskSpy: ReturnType<typeof vi.fn>;
let isGroupTaskRunningSpy: ReturnType<typeof vi.fn>;

vi.mock("../../tasks/TaskCenterContext", () => ({
  useTaskCenter: () => ({
    trackSubmittedTask: trackSubmittedTaskSpy,
    isGroupTaskRunning: isGroupTaskRunningSpy,
  }),
}));

function resetStore(overrides: Partial<AppStoreState> = {}) {
  useAppStore.setState(
    {
      ...INITIAL_STORE_STATE,
      selectedAssetName: "asset-a",
      currentMarkdownPath: "group_data/2/tutor_data/3/focus.md",
      activeTaskPanel: false,
      importDialogOpen: true,
      markdownContextMenuRequest: null,
      groupDiveRequest: null,
      assetDeleteRequest: null,
      ...overrides,
    },
    true,
  );
}

function createApi(): ExocortexApi {
  return {
    mode: "mock",
    capabilities: {
      deleteQuestion: true,
      deleteTutorSession: true,
    },
    system: {
      getConfig: vi.fn(async () => DEFAULT_SYSTEM_CONFIG),
      updateConfig: vi.fn(async (config) => ({ ...DEFAULT_SYSTEM_CONFIG, ...config })),
    },
    assets: {
      list: vi.fn(async () => []),
      getState: vi.fn(async () => ({
        asset: { name: "asset-a", pageCount: 1, pdfPath: "asset-a/raw.pdf" },
        references: [],
        blocks: [],
        mergeOrder: [],
        disabledContentItemIndexes: [],
        nextBlockId: 1,
        groups: [{ groupIdx: 2, blockIds: [] }],
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
      })),
      updateUiState: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      importAsset: vi.fn(async (_input: ImportAssetInput) => ({
        ...SUBMITTED_TASK,
        kind: "asset_init",
        title: "Asset init",
      })),
      deleteAsset: vi.fn(async () => undefined),
      revealAsset: vi.fn(async () => undefined),
    },
    markdown: {
      getTree: vi.fn(async () => []),
      getContent: vi.fn(async () => ({ path: "", title: "", html: "" })),
      getReference: vi.fn(async () => ""),
      renameNodeAlias: vi.fn(async () => ({ nodeId: "", path: null, title: "" })),
      reorderSiblings: vi.fn(async () => ({ parentId: null, orderedNodeIds: [] })),
    },
    pdf: {
      buildFileUrl: vi.fn(() => "/api/assets/asset-a/pdf/file"),
      getMetadata: vi.fn(async () => ({
        pageCount: 1,
        pageSizes: [{ width: 100, height: 100 }],
        defaultDpi: 130,
        minDpi: 72,
        maxDpi: 1200,
      })),
      getPageTextBoxes: vi.fn(async () => ({
        pageIndex: 0,
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
      previewMergeMarkdown: vi.fn(async () => ({ markdown: "" })),
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
      createTutorSession: vi.fn(async () => ({ tutorIdx: 3, markdownPath: "group_data/2/tutor_data/3/focus.md" })),
      submitGroupDive: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "group_dive", title: "Group dive" })),
      submitAskTutor: vi.fn(async () => SUBMITTED_TASK),
      submitReTutor: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "re_tutor", title: "Re Tutor" })),
      submitIntegrate: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "integrate", title: "Integrate" })),
      submitBugFinder: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "bug_finder", title: "Bug Finder" })),
      submitStudentNote: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "student_note", title: "Student Note" })),
      submitFixLatex: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "fix_latex", title: "Fix LaTeX" })),
      submitCompressPreview: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "compress_preview", title: "Compress Preview" })),
      submitCompressExecute: vi.fn(async () => ({ ...SUBMITTED_TASK, kind: "compress_execute", title: "Compress Execute" })),
      deleteQuestion: vi.fn(async () => undefined),
      deleteTutorSession: vi.fn(async () => undefined),
    },
  };
}

function Harness() {
  const controller = useWorkflowCommandController();

  return (
    <>
      <button
        type="button"
        onClick={() => {
          controller.setQuestionText("Why?");
        }}
      >
        prime-question
      </button>
      <button
        type="button"
        onClick={() => {
          void controller.handleAskTutor();
        }}
      >
        ask
      </button>
      <button
        type="button"
        onClick={() => {
          void controller.handleImportSubmit({
            assetName: "asset-new",
            assetSubfolder: "",
            sourceFile: new File(["pdf"], "demo.pdf", { type: "application/pdf" }),
            markdownFile: new File(["# demo"], "demo.md", { type: "text/markdown" }),
            contentListFile: new File(["[]"], "content_list.json", { type: "application/json" }),
          });
        }}
      >
        import
      </button>
      <div data-testid="active-task-panel">{String(controller.activeTaskPanel)}</div>
    </>
  );
}

describe("useWorkflowCommandController", () => {
  beforeEach(() => {
    trackSubmittedTaskSpy = vi.fn();
    isGroupTaskRunningSpy = vi.fn(() => false);
    resetStore();
  });

  afterEach(() => {
    useAppStore.setState(INITIAL_STORE_STATE, true);
    vi.restoreAllMocks();
  });

  it("does not auto-open the workflow modal after ask tutor submission", async () => {
    const setActiveTaskPanel = vi.fn();
    resetStore({
      setActiveTaskPanel,
      selectedAssetName: "asset-a",
      currentMarkdownPath: "group_data/2/tutor_data/3/focus.md",
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={createApi()}>
          <ToastProvider>
            <Harness />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "prime-question" }));
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "ask" }));
    });

    await waitFor(() => {
      expect(trackSubmittedTaskSpy).toHaveBeenCalledWith(SUBMITTED_TASK);
    });
    expect(setActiveTaskPanel).not.toHaveBeenCalledWith(true);
    expect(screen.getByTestId("active-task-panel").textContent).toBe("false");
  });

  it("does not auto-open the workflow modal after import submission", async () => {
    const setActiveTaskPanel = vi.fn();
    resetStore({
      setActiveTaskPanel,
      importDialogOpen: true,
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={createApi()}>
          <ToastProvider>
            <Harness />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "import" }));
    });

    await waitFor(() => {
      expect(trackSubmittedTaskSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: "asset_init",
        }),
      );
    });
    expect(setActiveTaskPanel).not.toHaveBeenCalledWith(true);
    expect(screen.getByTestId("active-task-panel").textContent).toBe("false");
  });

  it("does not auto-open the workflow modal after group dive submission", async () => {
    const setActiveTaskPanel = vi.fn();
    resetStore({
      setActiveTaskPanel,
      groupDiveRequest: {
        assetName: "asset-a",
        groupIdx: 5,
        nonce: Date.now(),
      },
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={createApi()}>
          <ToastProvider>
            <Harness />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(trackSubmittedTaskSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: "group_dive",
        }),
      );
    });
    expect(setActiveTaskPanel).not.toHaveBeenCalledWith(true);
    expect(screen.getByTestId("active-task-panel").textContent).toBe("false");
  });

  it("blocks duplicate group dive requests for the same group with a toast", async () => {
    isGroupTaskRunningSpy.mockReturnValue(true);
    const api = createApi();
    resetStore({
      groupDiveRequest: {
        assetName: "asset-a",
        groupIdx: 5,
        nonce: Date.now(),
      },
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={api}>
          <ToastProvider>
            <Harness />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Group 5 is already in progress.")).toBeInTheDocument();
    expect(api.workflows.submitGroupDive).not.toHaveBeenCalled();
    expect(trackSubmittedTaskSpy).not.toHaveBeenCalled();
  });
});
