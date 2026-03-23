import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../../app/api/ExocortexApiContext";
import type { ExocortexApi } from "../../../app/api/exocortexApi";
import { useAppStore } from "../../../app/store/appStore";
import type { AppStoreState } from "../../../app/store/appStore";
import type { AssetState, MarkdownTreeNode } from "../../../app/types";
import { ToastProvider } from "../../tasks/ToastProvider";
import type { TaskDetail } from "../../../generated/contracts";
import { useWorkflowTaskEffectsBridge } from "./useWorkflowTaskEffectsBridge";
import type { PendingImportIntent } from "./types";

const DEFAULT_SYSTEM_CONFIG = {
  themeMode: "light" as const,
  sidebarTextLineClamp: 1,
  sidebarFontSizePx: 14,
  tutorReasoningEffort: "medium" as const,
  tutorWithGlobalContext: true,
};

let taskCenterState: {
  tasks: TaskDetail[];
  tasksById: Record<string, TaskDetail>;
};

vi.mock("../../tasks/TaskCenterContext", () => ({
  useTaskCenter: () => taskCenterState,
}));

const INITIAL_STORE_STATE = useAppStore.getState();

function resetStore(overrides: Partial<AppStoreState> = {}) {
  useAppStore.setState(
    {
      ...INITIAL_STORE_STATE,
      selectedAssetName: null,
      currentMarkdownPath: null,
      openTabs: [],
      appMode: "normal",
      ...overrides,
    },
    true,
  );
}

function createTaskDetail(options: {
  id: string;
  kind: string;
  status: "completed" | "failed";
  assetName: string | null;
  artifactPath?: string | null;
  payload?: Record<string, unknown> | null;
}): TaskDetail {
  const event = {
    taskId: options.id,
    kind: options.kind,
    assetName: options.assetName,
    status: options.status,
    eventType: options.status === "completed" ? "completed" : "failed",
    message: options.status === "completed" ? "done" : "failed",
    progress: options.status === "completed" ? 1 : null,
    artifactPath: options.artifactPath ?? null,
    payload: options.payload ?? null,
    timestamp: "2026-03-22T12:00:00Z",
  } as const;

  return {
    id: options.id,
    kind: options.kind,
    status: options.status,
    title: options.kind,
    assetName: options.assetName,
    createdAt: event.timestamp,
    updatedAt: event.timestamp,
    events: [event],
    latestEvent: event,
    result: null,
  };
}

function createAssetState(assetName: string): AssetState {
  return {
    asset: {
      name: assetName,
      pageCount: 8,
      pdfPath: `${assetName}/raw.pdf`,
    },
    references: ["background.md", "concept.md", "formula.md"],
    blocks: [],
    mergeOrder: [],
    nextBlockId: 1,
    groups: [{ groupIdx: 1, blockIds: [] }],
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
}

function createApi(overrides: {
  assetState?: AssetState;
  markdownTree?: MarkdownTreeNode[];
} = {}): ExocortexApi {
  const assetState = overrides.assetState ?? createAssetState("asset-a");
  const markdownTree = overrides.markdownTree ?? [];

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
      getState: vi.fn(async () => assetState),
      updateUiState: vi.fn(async () => assetState),
      importAsset: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      deleteAsset: vi.fn(async () => undefined),
      revealAsset: vi.fn(async () => undefined),
    },
    markdown: {
      getTree: vi.fn(async () => markdownTree),
      getContent: vi.fn(async () => ({ path: "", title: "", html: "" })),
      getReference: vi.fn(async () => ""),
      renameNodeAlias: vi.fn(async () => ({ nodeId: "", path: null, title: "" })),
      reorderSiblings: vi.fn(async () => ({ parentId: null, orderedNodeIds: [] })),
    },
    pdf: {
      buildFileUrl: vi.fn(() => "/api/assets/asset-a/pdf/file"),
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
      createBlock: vi.fn(async () => assetState),
      deleteBlock: vi.fn(async () => assetState),
      deleteGroup: vi.fn(async () => assetState),
      updateSelection: vi.fn(async () => assetState),
      mergeGroup: vi.fn(async () => assetState),
      updateUiState: vi.fn(async () => assetState),
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

function BridgeHarness({
  pendingImportIntent,
  setPendingImportIntent = vi.fn(),
}: {
  pendingImportIntent: PendingImportIntent | null;
  setPendingImportIntent?: (intent: PendingImportIntent | null) => void;
}) {
  useWorkflowTaskEffectsBridge({
    pendingImportIntent,
    setPendingImportIntent,
    setCompressPreview: vi.fn(),
    feynman: null,
    setFeynman: vi.fn(),
  });
  return null;
}

describe("useWorkflowTaskEffectsBridge", () => {
  beforeEach(() => {
    resetStore();
    taskCenterState = {
      tasks: [],
      tasksById: {},
    };
  });

  afterEach(() => {
    useAppStore.setState(INITIAL_STORE_STATE, true);
    vi.restoreAllMocks();
  });

  it("opens completed group dive markdown artifacts", async () => {
    const task = createTaskDetail({
      id: "task-group",
      kind: "group_dive",
      status: "completed",
      assetName: "asset-a",
      artifactPath: "group_data/1/img_explainer_data/enhanced.md",
    });
    taskCenterState = {
      tasks: [task],
      tasksById: { [task.id]: task },
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={createApi()}>
          <ToastProvider>
            <BridgeHarness pendingImportIntent={null} />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(useAppStore.getState().currentMarkdownPath).toBe("group_data/1/img_explainer_data/enhanced.md");
    });
  });

  it("opens ask-history markdown for completed ask tutor tasks", async () => {
    const task = createTaskDetail({
      id: "task-ask",
      kind: "ask_tutor",
      status: "completed",
      assetName: "asset-a",
      artifactPath: "group_data/1/tutor_data/1/ask_history/2.md",
    });
    taskCenterState = {
      tasks: [task],
      tasksById: { [task.id]: task },
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={createApi()}>
          <ToastProvider>
            <BridgeHarness pendingImportIntent={null} />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      const openTab = useAppStore.getState().openTabs[0];
      expect(openTab?.path).toBe("group_data/1/tutor_data/1/ask_history/2.md");
      expect(openTab?.kind).toBe("ask");
    });
  });

  it("auto-opens an initial markdown after normal asset import completes", async () => {
    const task = createTaskDetail({
      id: "task-import",
      kind: "asset_init",
      status: "completed",
      assetName: "asset-new",
      artifactPath: "asset-new",
    });
    taskCenterState = {
      tasks: [task],
      tasksById: { [task.id]: task },
    };

    const assetState = createAssetState("asset-new");
    const markdownTree: MarkdownTreeNode[] = [
      {
        id: "group:1",
        kind: "group",
        title: "Group 1",
        path: "group_data/1/img_explainer_data/enhanced.md",
        children: [
          {
            id: "group:1:initial",
            kind: "markdown",
            title: "1.md",
            path: "group_data/1/img_explainer_data/initial/1.md",
            children: [],
          },
        ],
      },
    ];
    const setPendingImportIntent = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={createApi({ assetState, markdownTree })}>
          <ToastProvider>
            <BridgeHarness
              pendingImportIntent={{
                taskId: task.id,
              }}
              setPendingImportIntent={setPendingImportIntent}
            />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(useAppStore.getState().selectedAssetName).toBe("asset-new");
      expect(useAppStore.getState().currentMarkdownPath).toBe("group_data/1/img_explainer_data/initial/1.md");
    });

    expect(setPendingImportIntent).toHaveBeenCalledWith(null);
  });

  it("falls back to a reference tab when imported assets have no markdown landing page", async () => {
    const task = createTaskDetail({
      id: "task-import-no-markdown",
      kind: "asset_init",
      status: "completed",
      assetName: "asset-empty",
      artifactPath: "asset-empty",
    });
    taskCenterState = {
      tasks: [task],
      tasksById: { [task.id]: task },
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ExocortexApiProvider api={createApi({ assetState: createAssetState("asset-empty") })}>
          <ToastProvider>
            <BridgeHarness
              pendingImportIntent={{
                taskId: task.id,
              }}
            />
          </ToastProvider>
        </ExocortexApiProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(useAppStore.getState().selectedAssetName).toBe("asset-empty");
    });

    expect(useAppStore.getState().openTabs).toEqual([
      expect.objectContaining({
        assetName: "asset-empty",
        path: "references/background.md",
        kind: "reference",
      }),
    ]);
  });
});
