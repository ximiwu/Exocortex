import type { ComponentProps } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExocortexApiProvider } from "../../../app/api/ExocortexApiContext";
import type { AppSystemConfig } from "../../../app/api/types";
import type { ExocortexApi } from "../../../app/api/exocortexApi";
import { WorkflowTutorDock } from "./WorkflowTutorDock";

const DEFAULT_SYSTEM_CONFIG: AppSystemConfig = {
  themeMode: "light",
  sidebarTextLineClamp: 1,
  sidebarFontSizePx: 14,
  tutorReasoningEffort: "medium",
  tutorWithGlobalContext: true,
};

function createApi(options: {
  getConfig?: () => Promise<AppSystemConfig>;
  updateConfig?: ReturnType<typeof vi.fn>;
} = {}): ExocortexApi {
  const updateConfig =
    options.updateConfig ??
    vi.fn(async (config) => ({
      ...DEFAULT_SYSTEM_CONFIG,
      ...config,
    }));

  return {
    mode: "mock",
    capabilities: {
      deleteQuestion: true,
      deleteTutorSession: true,
    },
    system: {
      getConfig: vi.fn(options.getConfig ?? (async () => DEFAULT_SYSTEM_CONFIG)),
      updateConfig,
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

function renderDock(api: ExocortexApi) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={client}>
      <ExocortexApiProvider api={api}>
        <WorkflowTutorDock
          visible
          questionText=""
          effectiveTutorIdx={1}
          canSubmit={false}
          onQuestionChange={vi.fn()}
          onSubmit={vi.fn()}
        />
      </ExocortexApiProvider>
    </QueryClientProvider>,
  );
}

function renderDockWithProps(
  api: ExocortexApi,
  props: Partial<ComponentProps<typeof WorkflowTutorDock>> = {},
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  const defaultProps: ComponentProps<typeof WorkflowTutorDock> = {
    visible: true,
    questionText: "",
    effectiveTutorIdx: 1,
    canSubmit: false,
    onQuestionChange: vi.fn(),
    onSubmit: vi.fn(),
  };

  render(
    <QueryClientProvider client={client}>
      <ExocortexApiProvider api={api}>
        <WorkflowTutorDock {...defaultProps} {...props} />
      </ExocortexApiProvider>
    </QueryClientProvider>,
  );
}

describe("WorkflowTutorDock", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the persisted reasoning effort label", async () => {
    const api = createApi({
      getConfig: async () => ({
        ...DEFAULT_SYSTEM_CONFIG,
        tutorReasoningEffort: "xhigh",
      }),
    });

    renderDock(api);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Tutor ask settings" })).toHaveTextContent("extra high");
    });
  });

  it("opens and closes the settings popover", async () => {
    const api = createApi();
    renderDock(api);

    const trigger = await screen.findByRole("button", { name: "Tutor ask settings" });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "Tutor ask settings panel" })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Tutor ask settings panel" })).not.toBeInTheDocument();
    });

    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "Tutor ask settings panel" })).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Tutor ask settings panel" })).not.toBeInTheDocument();
    });
  });

  it("persists reasoning effort and global context immediately", async () => {
    const updateConfig = vi.fn(async (config) => ({
      ...DEFAULT_SYSTEM_CONFIG,
      ...config,
    }));
    const api = createApi({ updateConfig });
    renderDock(api);

    fireEvent.click(await screen.findByRole("button", { name: "Tutor ask settings" }));
    fireEvent.click(screen.getByRole("button", { name: "extra high" }));

    await waitFor(() => {
      expect(updateConfig).toHaveBeenCalledWith({ tutorReasoningEffort: "xhigh" });
    });
    expect(screen.getByRole("button", { name: "Tutor ask settings" })).toHaveTextContent("extra high");

    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => {
      expect(updateConfig).toHaveBeenCalledWith({ tutorWithGlobalContext: false });
    });
  });

  it("defaults to checked global context when config loading fails", async () => {
    const api = createApi({
      getConfig: async () => {
        throw new Error("failed");
      },
    });
    renderDock(api);

    fireEvent.click(await screen.findByRole("button", { name: "Tutor ask settings" }));
    expect(screen.getByRole("button", { name: "Tutor ask settings" })).toHaveTextContent("medium");
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("submits on Enter in the question field", async () => {
    const api = createApi();
    const onSubmit = vi.fn();
    renderDockWithProps(api, {
      questionText: "follow-up",
      canSubmit: true,
      onSubmit,
    });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Question for tutor 1" }), {
      key: "Enter",
    });

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("keeps Shift+Enter for a newline instead of submitting", async () => {
    const api = createApi();
    const onSubmit = vi.fn();
    renderDockWithProps(api, {
      questionText: "follow-up",
      canSubmit: true,
      onSubmit,
    });

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Question for tutor 1" }), {
      key: "Enter",
      shiftKey: true,
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
