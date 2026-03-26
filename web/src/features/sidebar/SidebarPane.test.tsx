import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../app/api/ExocortexApiContext";
import type { AppSystemConfig } from "../../app/api/types";
import type { ExocortexApi } from "../../app/api/exocortexApi";
import { queryKeys } from "../../app/api/exocortexApi";
import type { AppStoreState } from "../../app/store/appStore";
import { useAppStore } from "../../app/store/appStore";
import type { AssetState, MarkdownTreeNode } from "../../app/types";
import type { TaskDetail, TaskSummary } from "../../generated/contracts";
import { TaskCenterProvider } from "../tasks/TaskCenterContext";
import { ToastProvider } from "../tasks/ToastProvider";
import { SidebarPane } from "./SidebarPane";

const DEFAULT_SYSTEM_CONFIG: AppSystemConfig = {
  themeMode: "light",
  sidebarTextLineClamp: 1,
  sidebarFontSizePx: 14,
  tutorReasoningEffort: "medium",
  tutorWithGlobalContext: true,
};

const INITIAL_STORE_STATE = useAppStore.getState();

const GROUP_PATH = "group_data/7/img_explainer_data/enhanced.md";

const TREE: MarkdownTreeNode[] = [
  {
    id: "group:7",
    kind: "group",
    title: "Group 7",
    path: GROUP_PATH,
    children: [],
  },
];

const ASSET_STATE: AssetState = {
  asset: {
    name: "asset-a",
    pageCount: 12,
    pdfPath: "asset-a.pdf",
  },
  references: [],
  blocks: [
    {
      blockId: 21,
      pageIndex: 4,
      fractionRect: { x: 0.01, y: 0.01, width: 0.3, height: 0.2 },
      groupIdx: 7,
    },
  ],
  mergeOrder: [],
  disabledContentItemIndexes: [],
  nextBlockId: 22,
  groups: [
    {
      groupIdx: 7,
      blockIds: [21],
    },
  ],
  uiState: {
    currentPage: 1,
    zoom: 1,
    pdfScrollFraction: 0,
    pdfScrollLeftFraction: 0,
    currentMarkdownPath: GROUP_PATH,
    openMarkdownPaths: [GROUP_PATH],
    sidebarCollapsed: false,
    sidebarCollapsedNodeIds: [],
    markdownScrollFractions: {},
    sidebarWidthRatio: 0.2,
    rightRailWidthRatio: 0.25,
  },
};

function resetStore(overrides: Partial<AppStoreState> = {}) {
  useAppStore.setState(
    {
      ...INITIAL_STORE_STATE,
      selectedAssetName: "asset-a",
      currentMarkdownPath: GROUP_PATH,
      openTabs: [
        {
          assetName: "asset-a",
          path: GROUP_PATH,
          title: "Group 7",
          kind: "group",
        },
      ],
      sidebarCollapsed: false,
      sidebarCollapsedNodeIdsByAsset: {
        "asset-a": [],
      },
      pdfNavigationRequest: null,
      ...overrides,
    },
    true,
  );
}

function createTaskSummary(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "task-flashcard-1",
    kind: "flashcard",
    status: "queued",
    title: "Flashcard: group 7",
    assetName: "asset-a",
    createdAt: "2026-03-26T12:00:00Z",
    updatedAt: "2026-03-26T12:00:00Z",
    ...overrides,
  };
}

function createTaskDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    ...createTaskSummary(overrides),
    events: [],
    latestEvent: null,
    result: null,
  };
}

function createApi(options: {
  taskSummaries?: TaskSummary[];
  taskDetails?: Record<string, TaskDetail>;
  submitFlashcard?: ExocortexApi["workflows"]["submitFlashcard"];
} = {}): ExocortexApi {
  const taskDetails = options.taskDetails ?? {};
  const submitFlashcard =
    options.submitFlashcard ?? (vi.fn(async () => createTaskSummary()) as ExocortexApi["workflows"]["submitFlashcard"]);

  return {
    mode: "mock",
    capabilities: {
      deleteQuestion: true,
      deleteTutorSession: true,
    },
    system: {
      getConfig: vi.fn((): Promise<AppSystemConfig> => new Promise(() => {})),
      updateConfig: vi.fn(async (config) => ({ ...DEFAULT_SYSTEM_CONFIG, ...config })),
    },
    assets: {
      list: vi.fn(async () => []),
      getState: vi.fn(async () => ASSET_STATE),
      updateUiState: vi.fn(async () => ASSET_STATE),
      importAsset: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      deleteAsset: vi.fn(async () => undefined),
      revealAsset: vi.fn(async () => undefined),
    },
    markdown: {
      getTree: vi.fn(async () => TREE),
      getContent: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      getReference: vi.fn(async () => ""),
      renameNodeAlias: vi.fn(async () => ({
        nodeId: "group:7",
        path: GROUP_PATH,
        title: "Group 7",
      })),
      reorderSiblings: vi.fn(async () => ({
        parentId: null,
        orderedNodeIds: [],
      })),
    },
    pdf: {
      buildFileUrl: vi.fn(() => "/api/assets/asset-a/pdf/file"),
      getMetadata: vi.fn(async () => ({
        pageCount: 12,
        pageSizes: [],
        defaultDpi: 130,
        minDpi: 72,
        maxDpi: 300,
      })),
      getPageTextBoxes: vi.fn(async (_assetName, pageIndex) => ({
        pageIndex,
        items: [],
      })),
      searchContent: vi.fn(async (_assetName, query) => ({ query, matches: [] })),
      createBlock: vi.fn(async () => ASSET_STATE),
      deleteBlock: vi.fn(async () => ASSET_STATE),
      deleteGroup: vi.fn(async () => ASSET_STATE),
      updateDisabledContentItems: vi.fn(async () => ASSET_STATE),
      updateSelection: vi.fn(async () => ASSET_STATE),
      previewMergeMarkdown: vi.fn(async () => ({ markdown: "" })),
      mergeGroup: vi.fn(async () => ASSET_STATE),
      updateUiState: vi.fn(async () => ASSET_STATE),
    },
    tasks: {
      list: vi.fn(async () => options.taskSummaries ?? []),
      get: vi.fn(async (taskId: string) => taskDetails[taskId] ?? createTaskDetail({ id: taskId })),
      subscribe: vi.fn(() => () => undefined),
    },
    workflows: {
      createTutorSession: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitGroupDive: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      submitFlashcard,
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
}

describe("SidebarPane locate-in-pdf", () => {
  beforeEach(() => {
    resetStore();
  });

  afterEach(() => {
    useAppStore.setState(INITIAL_STORE_STATE, true);
    vi.restoreAllMocks();
  });

  it("requests PDF navigation for the first block page of the selected group", async () => {
    const api = createApi();
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    client.setQueryData(queryKeys.assetState("asset-a"), ASSET_STATE);

    await act(async () => {
      render(
        <QueryClientProvider client={client}>
          <ExocortexApiProvider api={api}>
            <ToastProvider>
              <TaskCenterProvider>
                <SidebarPane markdownTree={TREE} treeLoading={false} treeError={null} />
              </TaskCenterProvider>
            </ToastProvider>
          </ExocortexApiProvider>
        </QueryClientProvider>,
      );
      await Promise.resolve();
    });

    const groupButton = await screen.findByRole("button", { name: "Group 7" });
    await act(async () => {
      fireEvent.contextMenu(groupButton, {
        clientX: 32,
        clientY: 48,
      });
    });
    await act(async () => {
      fireEvent.click(await screen.findByRole("menuitem", { name: "locate in pdf" }));
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(useAppStore.getState().pdfNavigationRequest).toEqual(
        expect.objectContaining({
          assetName: "asset-a",
          page: 5,
        }),
      );
    });
  });

  it("submits flashcard generation from the group context menu", async () => {
    const submittedTask = createTaskSummary();
    const submitFlashcard = vi.fn(async () => submittedTask);
    const api = createApi({
      submitFlashcard,
      taskDetails: {
        [submittedTask.id]: createTaskDetail({ id: submittedTask.id }),
      },
    });
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    await act(async () => {
      render(
        <QueryClientProvider client={client}>
          <ExocortexApiProvider api={api}>
            <ToastProvider>
              <TaskCenterProvider>
                <SidebarPane markdownTree={TREE} treeLoading={false} treeError={null} />
              </TaskCenterProvider>
            </ToastProvider>
          </ExocortexApiProvider>
        </QueryClientProvider>,
      );
      await Promise.resolve();
    });

    const groupButton = await screen.findByRole("button", { name: "Group 7" });
    await act(async () => {
      fireEvent.contextMenu(groupButton, { clientX: 32, clientY: 48 });
    });
    await act(async () => {
      fireEvent.click(await screen.findByRole("menuitem", { name: "gen flashcard" }));
      await Promise.resolve();
    });

    expect(submitFlashcard).toHaveBeenCalledWith({
      assetName: "asset-a",
      groupIdx: 7,
    });
  });

  it("reveals the flashcard export directory from the group context menu", async () => {
    const api = createApi();
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    await act(async () => {
      render(
        <QueryClientProvider client={client}>
          <ExocortexApiProvider api={api}>
            <ToastProvider>
              <TaskCenterProvider>
                <SidebarPane markdownTree={TREE} treeLoading={false} treeError={null} />
              </TaskCenterProvider>
            </ToastProvider>
          </ExocortexApiProvider>
        </QueryClientProvider>,
      );
      await Promise.resolve();
    });

    const groupButton = await screen.findByRole("button", { name: "Group 7" });
    await act(async () => {
      fireEvent.contextMenu(groupButton, { clientX: 32, clientY: 48 });
    });
    await act(async () => {
      fireEvent.click(await screen.findByRole("menuitem", { name: "reveal flashcard" }));
      await Promise.resolve();
    });

    expect(api.assets.revealAsset).toHaveBeenCalledWith("asset-a", "group_data/7/flashcard/apkg");
  });

  it("warns instead of submitting when flashcard generation is already running", async () => {
    const runningTask = createTaskSummary({ id: "task-running", status: "running" });
    const api = createApi({
      taskSummaries: [runningTask],
      taskDetails: {
        "task-running": createTaskDetail({ id: "task-running", status: "running" }),
      },
      submitFlashcard: vi.fn(async () => createTaskSummary({ id: "task-should-not-run" })),
    });
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    await act(async () => {
      render(
        <QueryClientProvider client={client}>
          <ExocortexApiProvider api={api}>
            <ToastProvider>
              <TaskCenterProvider>
                <SidebarPane markdownTree={TREE} treeLoading={false} treeError={null} />
              </TaskCenterProvider>
            </ToastProvider>
          </ExocortexApiProvider>
        </QueryClientProvider>,
      );
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(api.tasks.list).toHaveBeenCalled();
    });

    const groupButton = await screen.findByRole("button", { name: "Group 7" });
    await act(async () => {
      fireEvent.contextMenu(groupButton, { clientX: 32, clientY: 48 });
    });
    await act(async () => {
      fireEvent.click(await screen.findByRole("menuitem", { name: "gen flashcard" }));
      await Promise.resolve();
    });

    expect(api.workflows.submitFlashcard).not.toHaveBeenCalled();
    expect(await screen.findByText("Flashcard already running")).toBeInTheDocument();
  });
});
