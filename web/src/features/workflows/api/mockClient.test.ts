import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createMockExocortexApi } from "./mockClient";

describe("mock workflow client task artifacts", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("completes ask tutor tasks with ask_history markdown artifacts", async () => {
    const api = createMockExocortexApi();
    const events: Array<{ taskId: string; eventType: string; artifactPath: string | null }> = [];
    const unsubscribe = api.subscribeToTaskEvents((event) => {
      events.push({
        taskId: event.taskId,
        eventType: event.eventType,
        artifactPath: event.artifactPath,
      });
    });

    const task = await api.submitAskTutor({
      assetName: "physics/paper_1",
      groupIdx: 1,
      tutorIdx: 1,
      question: "Why does the boundary term appear?",
    });

    await vi.advanceTimersByTimeAsync(250);

    const completedEvent = events.find(
      (event) => event.taskId === task.id && event.eventType === "completed",
    );
    expect(completedEvent?.artifactPath).toContain("/ask_history/");

    unsubscribe();
  });

  it("completes asset init tasks without pretending the artifact is markdown", async () => {
    const api = createMockExocortexApi();
    const events: Array<{ taskId: string; eventType: string; artifactPath: string | null }> = [];
    const unsubscribe = api.subscribeToTaskEvents((event) => {
      events.push({
        taskId: event.taskId,
        eventType: event.eventType,
        artifactPath: event.artifactPath,
      });
    });

    const task = await api.importAsset({
      sourceFile: new File(["%PDF"], "import.pdf", { type: "application/pdf" }),
      markdownFile: new File(["# Imported"], "import.md", { type: "text/markdown" }),
      contentListFile: new File(['{"items":[]}'], "content_list.json", { type: "application/json" }),
      assetName: "new-asset",
      assetSubfolder: "",
    });

    await vi.advanceTimersByTimeAsync(250);

    const completedEvent = events.find(
      (event) => event.taskId === task.id && event.eventType === "completed",
    );
    expect(completedEvent?.artifactPath?.endsWith(".md")).toBe(false);

    unsubscribe();
  });
});
