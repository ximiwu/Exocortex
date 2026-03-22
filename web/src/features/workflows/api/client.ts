import type {
  AssetState,
  AssetSummary,
  MarkdownContentPayload,
  MarkdownTreeNode,
  PdfMetadata,
  Rect,
  TaskDetail,
  TaskEvent,
  TaskSummary,
  TutorSession,
} from "../../../generated/contracts";
import type {
  BugFinderTaskPayload,
  ClientCapabilities,
  CompressTaskPayload,
  CreateTutorSessionPayload,
  DeleteQuestionPayload,
  FixLatexTaskPayload,
  GroupTaskPayload,
  ImportAssetPayload,
  IntegrateTaskPayload,
  TutorTaskPayload,
} from "./schema";
import { createMockExocortexApi } from "./mockClient";

export interface ExocortexClient {
  readonly mode: "live" | "mock";
  readonly capabilities: ClientCapabilities;
  listAssets(): Promise<AssetSummary[]>;
  getAssetState(assetName: string): Promise<AssetState>;
  getMarkdownTree(assetName: string): Promise<MarkdownTreeNode[]>;
  getMarkdownDocument(assetName: string, path: string): Promise<MarkdownContentPayload>;
  getReference(assetName: string, name: string): Promise<string>;
  updateAssetUiState(assetName: string, uiState: Partial<AssetState["uiState"]>): Promise<AssetState>;
  createTutorSession(payload: CreateTutorSessionPayload): Promise<TutorSession>;
  importAsset(payload: ImportAssetPayload): Promise<TaskSummary>;
  deleteAsset(assetName: string): Promise<void>;
  revealAsset(assetName: string, path?: string | null): Promise<void>;
  getPdfMetadata(assetName: string): Promise<PdfMetadata>;
  createBlock(assetName: string, input: { pageIndex: number; rect: Rect }): Promise<AssetState>;
  deleteBlock(assetName: string, blockId: number): Promise<AssetState>;
  deleteGroup(assetName: string, groupIdx: number): Promise<AssetState>;
  updateBlockSelection(assetName: string, mergeOrder: number[]): Promise<AssetState>;
  mergeGroup(
    assetName: string,
    blockIds: number[],
    options?: { markdownContent?: string | null; groupIdx?: number | null },
  ): Promise<AssetState>;
  updatePdfUiState(assetName: string, uiState: AssetState["uiState"]): Promise<AssetState>;
  listTasks(): Promise<TaskSummary[]>;
  getTask(taskId: string): Promise<TaskDetail>;
  subscribeToTaskEvents(listener: (event: TaskEvent) => void): () => void;
  submitGroupDive(payload: GroupTaskPayload): Promise<TaskSummary>;
  submitAskTutor(payload: TutorTaskPayload): Promise<TaskSummary>;
  submitReTutor(payload: TutorTaskPayload): Promise<TaskSummary>;
  submitIntegrate(payload: IntegrateTaskPayload): Promise<TaskSummary>;
  submitBugFinder(payload: BugFinderTaskPayload): Promise<TaskSummary>;
  submitStudentNote(payload: IntegrateTaskPayload): Promise<TaskSummary>;
  submitFixLatex(payload: FixLatexTaskPayload): Promise<TaskSummary>;
  submitCompressPreview(payload: CompressTaskPayload): Promise<TaskSummary>;
  submitCompressExecute(payload: CompressTaskPayload): Promise<TaskSummary>;
  renameMarkdownNodeAlias(payload: {
    assetName: string;
    nodeId: string;
    path?: string | null;
    alias: string;
  }): Promise<{ nodeId: string; path: string | null; title: string }>;
  reorderMarkdownSiblings(payload: {
    assetName: string;
    parentId?: string | null;
    orderedNodeIds: string[];
  }): Promise<{ parentId: string | null; orderedNodeIds: string[] }>;
  deleteQuestion(payload: DeleteQuestionPayload): Promise<void>;
}

export type ExocortexApi = ExocortexClient;
export type ExocortexApiMode = ExocortexApi["mode"];

export interface CreateExocortexApiOptions {
  mode?: ExocortexApiMode;
  apiBase?: string;
}

const DEFAULT_API_BASE = import.meta.env.VITE_EXOCORTEX_API_BASE ?? "/api";
let clientPromise: Promise<ExocortexClient> | null = null;

class HttpExocortexClient implements ExocortexClient {
  readonly mode = "live" as const;

  readonly capabilities: ClientCapabilities = {
    deleteQuestion: true,
  };

  constructor(private readonly apiBase: string) {}

  listAssets(): Promise<AssetSummary[]> {
    return this.requestJson("/assets");
  }

  getAssetState(assetName: string): Promise<AssetState> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/state`);
  }

  getMarkdownTree(assetName: string): Promise<MarkdownTreeNode[]> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/markdown/tree`);
  }

  getMarkdownDocument(assetName: string, path: string): Promise<MarkdownContentPayload> {
    return this.requestJson(
      `/assets/${encodeURIComponent(assetName)}/markdown/content?path=${encodeURIComponent(path)}`,
    );
  }

  getReference(assetName: string, name: string): Promise<string> {
    return this.requestText(`/assets/${encodeURIComponent(assetName)}/references/${encodeURIComponent(name)}`);
  }

  updateAssetUiState(assetName: string, uiState: Partial<AssetState["uiState"]>): Promise<AssetState> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/ui-state`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        currentPage: uiState.currentPage ?? null,
        zoom: uiState.zoom ?? null,
        pdfScrollFraction: uiState.pdfScrollFraction ?? null,
        pdfScrollLeftFraction: uiState.pdfScrollLeftFraction ?? null,
        currentMarkdownPath: uiState.currentMarkdownPath ?? null,
        openMarkdownPaths: uiState.openMarkdownPaths ?? null,
        sidebarCollapsed: uiState.sidebarCollapsed ?? null,
        sidebarCollapsedNodeIds: uiState.sidebarCollapsedNodeIds ?? null,
        markdownScrollFractions: uiState.markdownScrollFractions ?? null,
      }),
    });
  }

  async createTutorSession(payload: CreateTutorSessionPayload): Promise<TutorSession> {
    return this.requestJson(`/assets/${encodeURIComponent(payload.assetName)}/groups/${payload.groupIdx}/tutors`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        focusMarkdown: payload.focusMarkdown,
      }),
    });
  }

  importAsset(payload: ImportAssetPayload): Promise<TaskSummary> {
    const form = new FormData();
    form.set("source_file", payload.sourceFile);
    form.set("asset_name", payload.assetName);
    form.set("asset_subfolder", payload.assetSubfolder);
    form.set("compress_enabled", payload.compressEnabled ? "true" : "false");
    if (payload.skipImg2MdMarkdownFile) {
      form.set("skip_img2md_markdown_file", payload.skipImg2MdMarkdownFile);
    }
    return this.requestJson("/assets/import", {
      method: "POST",
      body: form,
    });
  }

  deleteAsset(assetName: string): Promise<void> {
    return this.requestVoid(`/assets/${encodeURIComponent(assetName)}`, { method: "DELETE" });
  }

  revealAsset(assetName: string, path?: string | null): Promise<void> {
    const suffix = path ? `?path=${encodeURIComponent(path)}` : "";
    return this.requestVoid(`/assets/${encodeURIComponent(assetName)}/reveal${suffix}`, { method: "POST" });
  }

  getPdfMetadata(assetName: string): Promise<PdfMetadata> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/pdf/metadata`);
  }

  createBlock(assetName: string, input: { pageIndex: number; rect: Rect }): Promise<AssetState> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/blocks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        pageIndex: input.pageIndex,
        rect: input.rect,
      }),
    });
  }

  deleteBlock(assetName: string, blockId: number): Promise<AssetState> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/blocks/${blockId}`, {
      method: "DELETE",
    });
  }

  deleteGroup(assetName: string, groupIdx: number): Promise<AssetState> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/groups/${groupIdx}`, {
      method: "DELETE",
    });
  }

  updateBlockSelection(assetName: string, mergeOrder: number[]): Promise<AssetState> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/blocks/selection`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        mergeOrder,
      }),
    });
  }

  mergeGroup(
    assetName: string,
    blockIds: number[],
    options: { markdownContent?: string | null; groupIdx?: number | null } = {},
  ): Promise<AssetState> {
    return this.requestJson(`/assets/${encodeURIComponent(assetName)}/groups/merge`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        blockIds,
        markdownContent: options.markdownContent ?? null,
        groupIdx: options.groupIdx ?? null,
      }),
    });
  }

  updatePdfUiState(assetName: string, uiState: AssetState["uiState"]): Promise<AssetState> {
    return this.updateAssetUiState(assetName, uiState);
  }

  listTasks(): Promise<TaskSummary[]> {
    return this.requestJson("/tasks");
  }

  getTask(taskId: string): Promise<TaskDetail> {
    return this.requestJson(`/tasks/${encodeURIComponent(taskId)}`);
  }

  subscribeToTaskEvents(listener: (event: TaskEvent) => void): () => void {
    const ws = new WebSocket(buildWsUrl(this.apiBase));

    ws.onmessage = (message) => {
      try {
        const raw = JSON.parse(String(message.data));
        listener(normalizeTaskEvent(raw));
      } catch (error) {
        console.warn("Failed to parse task event", error);
      }
    };

    return () => {
      ws.close();
    };
  }

  submitGroupDive(payload: GroupTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/group-dive", payload);
  }

  submitAskTutor(payload: TutorTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/ask-tutor", payload);
  }

  submitReTutor(payload: TutorTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/re-tutor", payload);
  }

  submitIntegrate(payload: IntegrateTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/integrate", payload);
  }

  submitBugFinder(payload: BugFinderTaskPayload): Promise<TaskSummary> {
    const form = new FormData();
    form.set("assetName", payload.assetName);
    form.set("groupIdx", String(payload.groupIdx));
    form.set("tutorIdx", String(payload.tutorIdx));
    for (const file of payload.manuscriptFiles) {
      form.append("manuscript_files", file);
    }
    return this.requestJson("/tasks/bug-finder", {
      method: "POST",
      body: form,
    });
  }

  submitStudentNote(payload: IntegrateTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/student-note", payload);
  }

  submitFixLatex(payload: FixLatexTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/fix-latex", payload);
  }

  submitCompressPreview(payload: CompressTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/compress-preview", payload);
  }

  submitCompressExecute(payload: CompressTaskPayload): Promise<TaskSummary> {
    return this.submitJsonTask("/tasks/compress-execute", payload);
  }

  async renameMarkdownNodeAlias(payload: {
    assetName: string;
    nodeId: string;
    path?: string | null;
    alias: string;
  }): Promise<{ nodeId: string; path: string | null; title: string }> {
    const response = await this.requestJson<{ details?: { nodeId?: string; path?: string | null; title?: string } }>(
      `/assets/${encodeURIComponent(payload.assetName)}/markdown/nodes/alias`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          nodeId: payload.nodeId,
          path: payload.path ?? null,
          alias: payload.alias,
        }),
      },
    );
    return {
      nodeId: String(response.details?.nodeId ?? payload.nodeId),
      path: typeof response.details?.path === "string" ? response.details.path : payload.path ?? null,
      title: String(response.details?.title ?? ""),
    };
  }

  async reorderMarkdownSiblings(payload: {
    assetName: string;
    parentId?: string | null;
    orderedNodeIds: string[];
  }): Promise<{ parentId: string | null; orderedNodeIds: string[] }> {
    const response = await this.requestJson<{ details?: { parentId?: string | null; orderedNodeIds?: string[] } }>(
      `/assets/${encodeURIComponent(payload.assetName)}/markdown/nodes/reorder`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          parentId: payload.parentId ?? null,
          orderedNodeIds: payload.orderedNodeIds,
        }),
      },
    );
    return {
      parentId: typeof response.details?.parentId === "string" ? response.details.parentId : payload.parentId ?? null,
      orderedNodeIds: Array.isArray(response.details?.orderedNodeIds)
        ? response.details.orderedNodeIds
        : payload.orderedNodeIds,
    };
  }

  deleteQuestion(payload: DeleteQuestionPayload): Promise<void> {
    return this.requestVoid(
      `/assets/${encodeURIComponent(payload.assetName)}/groups/${payload.groupIdx}/tutors/${payload.tutorIdx}/questions?path=${encodeURIComponent(payload.markdownPath)}`,
      {
        method: "DELETE",
      },
    );
  }

  private submitJsonTask<TPayload extends object>(path: string, payload: TPayload): Promise<TaskSummary> {
    return this.requestJson(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  }

  private async requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(buildApiUrl(path, this.apiBase), {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      throw await toRequestError(response);
    }

    return (await response.json()) as T;
  }

  private async requestText(path: string): Promise<string> {
    const response = await fetch(buildApiUrl(path, this.apiBase), {
      cache: "no-store",
    });
    if (!response.ok) {
      throw await toRequestError(response);
    }
    return response.text();
  }

  private async requestVoid(path: string, init?: RequestInit): Promise<void> {
    const response = await fetch(buildApiUrl(path, this.apiBase), {
      ...init,
      cache: "no-store",
    });
    if (!response.ok) {
      throw await toRequestError(response);
    }
  }
}

export function buildApiUrl(path: string, base = DEFAULT_API_BASE): string {
  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  return `${normalizedBase}${path.startsWith("/") ? path : `/${path}`}`;
}

export function buildPdfPageImageUrl(assetName: string, pageIndex: number, dpi: number): string {
  const safeDpi = Math.max(1, Math.round(dpi));
  return buildApiUrl(`/assets/${encodeURIComponent(assetName)}/pdf/pages/${pageIndex}/image?dpi=${safeDpi}`);
}

export function resolveExocortexApiMode(rawMode: unknown = import.meta.env.VITE_EXOCORTEX_API_MODE): ExocortexApiMode {
  if (typeof rawMode !== "string" || rawMode.trim() === "") {
    return "live";
  }

  const normalized = rawMode.trim().toLowerCase();
  if (normalized === "live" || normalized === "mock") {
    return normalized;
  }

  if (normalized === "auto") {
    console.warn('VITE_EXOCORTEX_API_MODE="auto" is deprecated; defaulting to "live".');
    return "live";
  }

  throw new Error(`Invalid VITE_EXOCORTEX_API_MODE: "${rawMode}". Expected "live" or "mock".`);
}

export function createExocortexApi(options: CreateExocortexApiOptions = {}): ExocortexApi {
  const mode = options.mode ?? resolveExocortexApiMode();
  if (mode === "mock") {
    return createMockExocortexApi();
  }

  return new HttpExocortexClient(options.apiBase ?? DEFAULT_API_BASE);
}

export async function getExocortexApi(): Promise<ExocortexApi> {
  return getExocortexClient();
}

export async function getExocortexClient(): Promise<ExocortexClient> {
  clientPromise ??= Promise.resolve(createExocortexApi());
  return clientPromise;
}

export const createExocortexClient = getExocortexClient;

export function resetExocortexClientForTests(): void {
  clientPromise = null;
}

function buildWsUrl(apiBase: string): string {
  const base = new URL(apiBase, window.location.origin);
  const protocol = base.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${base.host}${base.pathname.replace(/\/$/, "")}/ws/tasks`;
}

async function toRequestError(response: Response): Promise<Error> {
  try {
    const data = (await response.json()) as { error?: { message?: string } };
    return new Error(data.error?.message ?? `Request failed with ${response.status}.`);
  } catch {
    return new Error(`Request failed with ${response.status}.`);
  }
}

function normalizeTaskEvent(raw: unknown): TaskEvent {
  const record = isRecord(raw) ? raw : {};
  return {
    taskId: String(record.taskId ?? ""),
    kind: String(record.kind ?? "task"),
    status: normalizeTaskStatus(record.status),
    eventType: normalizeTaskEventType(record.eventType),
    message: String(record.message ?? ""),
    progress: typeof record.progress === "number" ? record.progress : null,
    artifactPath: typeof record.artifactPath === "string" ? record.artifactPath : null,
    payload: isRecord(record.payload) ? record.payload : null,
    timestamp: String(record.timestamp ?? new Date().toISOString()),
  };
}

function normalizeTaskStatus(raw: unknown): TaskSummary["status"] {
  return raw === "queued" || raw === "running" || raw === "completed" || raw === "failed"
    ? raw
    : "running";
}

function normalizeTaskEventType(raw: unknown): TaskEvent["eventType"] {
  return raw === "queued" ||
    raw === "started" ||
    raw === "progress" ||
    raw === "log" ||
    raw === "artifact" ||
    raw === "completed" ||
    raw === "failed"
    ? raw
    : "log";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
