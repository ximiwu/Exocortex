import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../app/api/ExocortexApiContext";
import type { ExocortexApi } from "../../app/api/exocortexApi";
import { TaskCenterProvider, useTaskCenter } from "./TaskCenterContext";
import { ToastProvider } from "./ToastProvider";

const DEFAULT_SYSTEM_CONFIG = {
  themeMode: "light" as const,
  sidebarTextLineClamp: 1,
  sidebarFontSizePx: 14,
  tutorReasoningEffort: "medium" as const,
  tutorWithGlobalContext: true,
};

const QUEUED_TASK = {
  id: "task-1",
  kind: "group_dive",
  status: "queued" as const,
  title: "Group dive",
  assetName: "asset-a",
  createdAt: "2026-03-22T12:00:00Z",
  updatedAt: "2026-03-22T12:00:00Z",
};

const QUEUED_DETAIL = {
  ...QUEUED_TASK,
  events: [],
  latestEvent: null,
  result: null,
};

const COMPLETED_EVENT = {
  taskId: "task-1",
  kind: "group_dive",
  assetName: "asset-a",
  status: "completed" as const,
  eventType: "completed" as const,
  message: "done",
  progress: 1,
  artifactPath: "group_data/1/img_explainer_data/enhanced.md",
  payload: null,
  timestamp: "2026-03-22T12:00:02Z",
};

const COMPLETED_DETAIL = {
  ...QUEUED_TASK,
  status: "completed" as const,
  updatedAt: "2026-03-22T12:00:02Z",
  events: [COMPLETED_EVENT],
  latestEvent: COMPLETED_EVENT,
  result: null,
};

function Harness() {
  const { tasks, trackSubmittedTask } = useTaskCenter();
  return (
    <>
      <button type="button" onClick={() => trackSubmittedTask(QUEUED_TASK)}>
        track
      </button>
      <div data-testid="statuses">{tasks.map((task) => `${task.id}:${task.status}`).join(",")}</div>
    </>
  );
}

function createApi(): ExocortexApi {
  const getTask = vi
    .fn()
    .mockResolvedValueOnce(QUEUED_DETAIL)
    .mockResolvedValueOnce(COMPLETED_DETAIL)
    .mockResolvedValue(COMPLETED_DETAIL);

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
      getState: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      updateUiState: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      importAsset: vi.fn(async () => QUEUED_TASK),
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
      get: getTask,
      subscribe: vi.fn(() => () => undefined),
    },
    workflows: {
      createTutorSession: vi.fn(async () => ({ tutorIdx: 1, markdownPath: "group_data/1/tutor_data/1/focus.md" })),
      submitGroupDive: vi.fn(async () => QUEUED_TASK),
      submitFlashcard: vi.fn(async () => QUEUED_TASK),
      submitAskTutor: vi.fn(async () => QUEUED_TASK),
      submitReTutor: vi.fn(async () => QUEUED_TASK),
      submitIntegrate: vi.fn(async () => QUEUED_TASK),
      submitBugFinder: vi.fn(async () => QUEUED_TASK),
      submitStudentNote: vi.fn(async () => QUEUED_TASK),
      submitFixLatex: vi.fn(async () => QUEUED_TASK),
      submitCompressPreview: vi.fn(async () => QUEUED_TASK),
      submitCompressExecute: vi.fn(async () => QUEUED_TASK),
      deleteQuestion: vi.fn(async () => undefined),
      deleteTutorSession: vi.fn(async () => undefined),
    },
  };
}

describe("TaskCenterProvider", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("shows submitted queued tasks immediately and polls them to completion", async () => {
    const api = createApi();

    render(
      <ExocortexApiProvider api={api}>
        <ToastProvider>
          <TaskCenterProvider>
            <Harness />
          </TaskCenterProvider>
        </ToastProvider>
      </ExocortexApiProvider>,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "track" }));
      await Promise.resolve();
    });

    expect(screen.getByTestId("statuses").textContent).toContain("task-1:queued");
    expect(screen.getByText("Started.")).toBeInTheDocument();
    expect(screen.getAllByText("Started.")).toHaveLength(1);

    expect(api.tasks.get).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersToNextTimerAsync();
    });

    expect(screen.getByTestId("statuses").textContent).toContain("task-1:completed");
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getAllByText("Started.")).toHaveLength(1);
  });
});
