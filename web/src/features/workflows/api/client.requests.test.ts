import { afterEach, describe, expect, it, vi } from "vitest";

import { createExocortexApi } from "./client";

describe("workflow api client requests", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("serializes asset ui state updates through the shared JSON request helper", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ asset: { name: "course/unit 1" }, uiState: {} }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = createExocortexApi({ mode: "live" });
    await client.updateAssetUiState("course/unit 1", {
      currentPage: 3,
      sidebarCollapsed: false,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/assets/course%2Funit%201/ui-state");
    expect(init.method).toBe("PUT");
    expect(init.cache).toBe("no-store");
    expect(init.headers).toMatchObject({
      Accept: "application/json",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(init.body))).toEqual({
      currentPage: 3,
      zoom: null,
      pdfScrollFraction: null,
      pdfScrollLeftFraction: null,
      currentMarkdownPath: null,
      openMarkdownPaths: null,
      sidebarCollapsed: false,
      sidebarCollapsedNodeIds: null,
      markdownScrollFractions: null,
      sidebarWidthRatio: null,
      rightRailWidthRatio: null,
    });
  });

  it("serializes markdown alias updates through the shared JSON request helper", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ details: { title: "Renamed node" } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = createExocortexApi({ mode: "live" });
    const result = await client.renameMarkdownNodeAlias({
      assetName: "course/unit 1",
      nodeId: "group:1",
      path: "group_data/1/file.md",
      alias: "Renamed node",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/assets/course%2Funit%201/markdown/nodes/alias");
    expect(init.method).toBe("PATCH");
    expect(init.headers).toMatchObject({
      Accept: "application/json",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(init.body))).toEqual({
      nodeId: "group:1",
      path: "group_data/1/file.md",
      alias: "Renamed node",
    });
    expect(result).toEqual({
      nodeId: "group:1",
      path: "group_data/1/file.md",
      title: "Renamed node",
    });
  });

  it("serializes asset import uploads through the shared form-data request helper", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "task-1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = createExocortexApi({ mode: "live" });
    await client.importAsset({
      sourceFile: new File(["pdf"], "source.pdf", { type: "application/pdf" }),
      markdownFile: new File(["# notes"], "notes.md", { type: "text/markdown" }),
      contentListFile: new File(["[]"], "content_list.json", { type: "application/json" }),
      assetName: "course/unit 1",
      assetSubfolder: "chapter-a",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const form = init.body as FormData;
    expect(url).toBe("/api/assets/import");
    expect(init.method).toBe("POST");
    expect(form.get("asset_name")).toBe("course/unit 1");
    expect(form.get("asset_subfolder")).toBe("chapter-a");
    expect((form.get("source_file") as File).name).toBe("source.pdf");
    expect((form.get("markdown_file") as File).name).toBe("notes.md");
    expect((form.get("content_list_file") as File).name).toBe("content_list.json");
  });

  it("serializes bug-finder uploads through the shared form-data request helper", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "task-2" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = createExocortexApi({ mode: "live" });
    await client.submitBugFinder({
      assetName: "course/unit 1",
      groupIdx: 4,
      tutorIdx: 2,
      manuscriptFiles: [
        new File(["a"], "draft-a.docx"),
        new File(["b"], "draft-b.docx"),
      ],
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const form = init.body as FormData;
    expect(url).toBe("/api/tasks/bug-finder");
    expect(init.method).toBe("POST");
    expect(form.get("assetName")).toBe("course/unit 1");
    expect(form.get("groupIdx")).toBe("4");
    expect(form.get("tutorIdx")).toBe("2");
    expect((form.getAll("manuscript_files") as File[]).map((file) => file.name)).toEqual([
      "draft-a.docx",
      "draft-b.docx",
    ]);
  });

  it("serializes flashcard requests through the shared JSON request helper", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "task-3" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = createExocortexApi({ mode: "live" });
    await client.submitFlashcard({
      assetName: "course/unit 1",
      groupIdx: 4,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/tasks/flashcard");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      Accept: "application/json",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(init.body))).toEqual({
      assetName: "course/unit 1",
      groupIdx: 4,
    });
  });

  it("serializes PDF search requests through the shared JSON request helper", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ query: "energy", matches: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = createExocortexApi({ mode: "live" });
    const result = await client.searchPdfContent("course/unit 1", "energy");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/assets/course%2Funit%201/pdf/search");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      Accept: "application/json",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(init.body))).toEqual({
      query: "energy",
    });
    expect(result).toEqual({
      query: "energy",
      matches: [],
    });
  });
});
