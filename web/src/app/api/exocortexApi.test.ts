import { describe, expect, it, vi } from "vitest";

import type { ExocortexApi as CoreExocortexApi } from "../../features/workflows/api/client";
import { buildPdfFileUrl, wrapCoreApi } from "./exocortexApi";

function createCoreStub(overrides: Partial<CoreExocortexApi> = {}): CoreExocortexApi {
  return {
    mode: "live",
    capabilities: {
      deleteQuestion: true,
      deleteTutorSession: true,
    },
    getSystemConfig: vi.fn(),
    updateSystemConfig: vi.fn(),
    listAssets: vi.fn(),
    getAssetState: vi.fn(),
    getMarkdownTree: vi.fn(),
    getMarkdownDocument: vi.fn(),
    getReference: vi.fn(),
    updateAssetUiState: vi.fn(),
    createTutorSession: vi.fn(),
    importAsset: vi.fn(),
    deleteAsset: vi.fn(),
    revealAsset: vi.fn(),
    getPdfMetadata: vi.fn(),
    getPdfPageTextBoxes: vi.fn(),
    searchPdfContent: vi.fn(),
    buildPdfFileUrl: vi.fn(),
    createBlock: vi.fn(),
    deleteBlock: vi.fn(),
    deleteGroup: vi.fn(),
    updateDisabledContentItems: vi.fn(),
    updateBlockSelection: vi.fn(),
    previewMergeMarkdown: vi.fn(),
    mergeGroup: vi.fn(),
    updatePdfUiState: vi.fn(),
    listTasks: vi.fn(),
    getTask: vi.fn(),
    subscribeToTaskEvents: vi.fn(),
    submitGroupDive: vi.fn(),
    submitAskTutor: vi.fn(),
    submitReTutor: vi.fn(),
    submitIntegrate: vi.fn(),
    submitBugFinder: vi.fn(),
    submitStudentNote: vi.fn(),
    submitFixLatex: vi.fn(),
    submitCompressPreview: vi.fn(),
    submitCompressExecute: vi.fn(),
    renameMarkdownNodeAlias: vi.fn(),
    reorderMarkdownSiblings: vi.fn(),
    deleteQuestion: vi.fn(),
    deleteTutorSession: vi.fn(),
    ...overrides,
  } as CoreExocortexApi;
}

describe("app exocortex api wrapper", () => {
  it("binds grouped methods to the core client and preserves capabilities", async () => {
    const unsubscribe = vi.fn();
    const core = createCoreStub({
      getSystemConfig: vi.fn().mockResolvedValue({ themeMode: "light" }),
      listAssets: vi.fn().mockResolvedValue([]),
      subscribeToTaskEvents: vi.fn().mockReturnValue(unsubscribe),
    });

    const api = wrapCoreApi(core);
    const listener = vi.fn();

    expect(api.mode).toBe("live");
    expect(api.capabilities).toBe(core.capabilities);
    await api.system.getConfig();
    await api.assets.list();

    expect(api.tasks.subscribe(listener)).toBe(unsubscribe);
    expect(core.getSystemConfig).toHaveBeenCalledTimes(1);
    expect(core.listAssets).toHaveBeenCalledTimes(1);
    expect(core.subscribeToTaskEvents).toHaveBeenCalledWith(listener);
    expect(api.pdf.buildFileUrl("course/unit 1")).toBe(buildPdfFileUrl("course/unit 1"));
  });

  it("normalizes markdown payloads into app-facing html content", async () => {
    const core = createCoreStub({
      getMarkdownDocument: vi.fn().mockResolvedValue({
        html: "<!DOCTYPE html><html><body><article><h1>Topic</h1></article></body></html>",
      }),
    });

    const api = wrapCoreApi(core);
    const result = await api.markdown.getContent("asset-a", "notes/topic.md");

    expect(core.getMarkdownDocument).toHaveBeenCalledWith("asset-a", "notes/topic.md");
    expect(result).toEqual({
      path: "notes/topic.md",
      title: "topic.md",
      html: "<article><h1>Topic</h1></article>",
    });
  });
});
