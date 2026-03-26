import { marked } from "marked";

import type {
  ApiSource,
  AssetState,
  AssetSummary,
  MarkdownContent,
  MarkdownTreeNode,
  PdfMetadata,
  TaskDetail,
  TaskEvent,
  TaskSummary,
  TutorSession,
} from "../../generated/contracts";
import {
  buildPdfFileUrl as buildClientPdfFileUrl,
  createExocortexApi as createCoreExocortexApi,
  type CreateExocortexApiOptions,
  type ExocortexApi as CoreExocortexApi,
} from "../../features/workflows/api/client";
import type {
  AppSystemConfig,
  AppSystemConfigUpdate,
  BugFinderTaskInput,
  ClientCapabilities,
  CompressTaskInput,
  CreateBlockInput,
  CreateTutorSessionInput,
  DeleteQuestionInput,
  DeleteTutorSessionInput,
  FixLatexTaskInput,
  FlashcardTaskInput,
  GroupTaskInput,
  ImportAssetInput,
  IntegrateTaskInput,
  PdfSearchResponse,
  MergeGroupInput,
  PdfPageTextBoxes,
  PreviewMergeMarkdownResponse,
  RenameMarkdownNodeAliasInput,
  ReorderMarkdownSiblingsInput,
  ReTutorTaskInput,
  TutorTaskInput,
} from "./types";

marked.setOptions({
  gfm: true,
});

export interface ExocortexApi {
  readonly mode: ApiSource;
  readonly capabilities: ClientCapabilities;
  readonly system: {
    getConfig(): Promise<AppSystemConfig>;
    updateConfig(config: AppSystemConfigUpdate): Promise<AppSystemConfig>;
  };
  readonly assets: {
    list(): Promise<AssetSummary[]>;
    getState(assetName: string): Promise<AssetState>;
    updateUiState(assetName: string, uiState: Partial<AssetState["uiState"]>): Promise<AssetState>;
    importAsset(input: ImportAssetInput): Promise<TaskSummary>;
    deleteAsset(assetName: string): Promise<void>;
    revealAsset(assetName: string, path?: string | null): Promise<void>;
  };
  readonly markdown: {
    getTree(assetName: string): Promise<MarkdownTreeNode[]>;
    getContent(assetName: string, path: string): Promise<MarkdownContent>;
    getReference(assetName: string, name: string): Promise<string>;
    renameNodeAlias(input: RenameMarkdownNodeAliasInput): Promise<{ nodeId: string; path: string | null; title: string }>;
    reorderSiblings(input: ReorderMarkdownSiblingsInput): Promise<{ parentId: string | null; orderedNodeIds: string[] }>;
  };
  readonly pdf: {
    buildFileUrl(assetName: string): string;
    getMetadata(assetName: string): Promise<PdfMetadata>;
    getPageTextBoxes(assetName: string, pageIndex: number): Promise<PdfPageTextBoxes>;
    searchContent(assetName: string, query: string): Promise<PdfSearchResponse>;
    createBlock(assetName: string, input: CreateBlockInput): Promise<AssetState>;
    deleteBlock(assetName: string, blockId: number): Promise<AssetState>;
    deleteGroup(assetName: string, groupIdx: number): Promise<AssetState>;
    updateDisabledContentItems(assetName: string, disabledContentItemIndexes: number[]): Promise<AssetState>;
    updateSelection(assetName: string, mergeOrder: number[]): Promise<AssetState>;
    previewMergeMarkdown(assetName: string, blockIds: number[]): Promise<PreviewMergeMarkdownResponse>;
    mergeGroup(assetName: string, blockIds: number[], options?: MergeGroupInput): Promise<AssetState>;
    updateUiState(assetName: string, uiState: AssetState["uiState"]): Promise<AssetState>;
  };
  readonly tasks: {
    list(): Promise<TaskSummary[]>;
    get(taskId: string): Promise<TaskDetail>;
    subscribe(listener: (event: TaskEvent) => void): () => void;
  };
  readonly workflows: {
    createTutorSession(input: CreateTutorSessionInput): Promise<TutorSession>;
    submitGroupDive(input: GroupTaskInput): Promise<TaskSummary>;
    submitFlashcard(input: FlashcardTaskInput): Promise<TaskSummary>;
    submitAskTutor(input: TutorTaskInput): Promise<TaskSummary>;
    submitReTutor(input: ReTutorTaskInput): Promise<TaskSummary>;
    submitIntegrate(input: IntegrateTaskInput): Promise<TaskSummary>;
    submitBugFinder(input: BugFinderTaskInput): Promise<TaskSummary>;
    submitStudentNote(input: IntegrateTaskInput): Promise<TaskSummary>;
    submitFixLatex(input: FixLatexTaskInput): Promise<TaskSummary>;
    submitCompressPreview(input: CompressTaskInput): Promise<TaskSummary>;
    submitCompressExecute(input: CompressTaskInput): Promise<TaskSummary>;
    deleteQuestion(input: DeleteQuestionInput): Promise<void>;
    deleteTutorSession(input: DeleteTutorSessionInput): Promise<void>;
  };
}

export const queryKeys = {
  assets: ["assets"] as const,
  systemConfig: ["system-config"] as const,
  assetState: (assetName: string | null) => ["asset-state", assetName] as const,
  markdownTree: (assetName: string | null) => ["markdown-tree", assetName] as const,
  pdfMetadata: (assetName: string | null) => ["pdf-metadata", assetName] as const,
  pdfPageTextBoxes: (assetName: string | null, pageIndex: number) =>
    ["pdf-page-text-boxes", assetName, pageIndex] as const,
  pdfSearch: (assetName: string | null, query: string, disabledSignature: string) =>
    ["pdf-search", assetName, query, disabledSignature] as const,
  markdownContent: (assetName: string | null, path: string | null) =>
    ["markdown-content", assetName, path] as const,
};

export const buildPdfFileUrl = buildClientPdfFileUrl;
export const buildFileUrl = buildPdfFileUrl;

export function createExocortexApi(options: CreateExocortexApiOptions = {}): ExocortexApi {
  return wrapCoreApi(createCoreExocortexApi(options));
}

export function wrapCoreApi(core: CoreExocortexApi): ExocortexApi {
  const bind = <Key extends CoreMethodKey>(key: Key) => bindCoreMethod(core, key);

  return {
    mode: core.mode,
    capabilities: core.capabilities,
    system: createSystemApi(bind),
    assets: createAssetApi(bind),
    markdown: createMarkdownApi(bind),
    pdf: createPdfApi(bind),
    tasks: createTaskApi(bind),
    workflows: createWorkflowApi(bind),
  };
}

type CoreMethodKey = {
  [Key in keyof CoreExocortexApi]: CoreExocortexApi[Key] extends (...args: infer _Args) => unknown ? Key : never;
}[keyof CoreExocortexApi];

function bindCoreMethod<Key extends CoreMethodKey>(
  core: CoreExocortexApi,
  key: Key,
): CoreExocortexApi[Key] {
  const method = core[key] as (...args: unknown[]) => unknown;
  return method.bind(core) as CoreExocortexApi[Key];
}

type BindCoreMethod = <Key extends CoreMethodKey>(key: Key) => CoreExocortexApi[Key];

function createSystemApi(bind: BindCoreMethod): ExocortexApi["system"] {
  return {
    getConfig: bind("getSystemConfig"),
    updateConfig: bind("updateSystemConfig"),
  };
}

function createAssetApi(bind: BindCoreMethod): ExocortexApi["assets"] {
  return {
    list: bind("listAssets"),
    getState: bind("getAssetState"),
    updateUiState: bind("updateAssetUiState"),
    importAsset: bind("importAsset"),
    deleteAsset: bind("deleteAsset"),
    revealAsset: bind("revealAsset"),
  };
}

function createMarkdownApi(bind: BindCoreMethod): ExocortexApi["markdown"] {
  const getMarkdownDocument = bind("getMarkdownDocument");
  return {
    getTree: bind("getMarkdownTree"),
    getContent: async (assetName, path) =>
      normalizeMarkdownContent(path, await getMarkdownDocument(assetName, path)),
    getReference: bind("getReference"),
    renameNodeAlias: bind("renameMarkdownNodeAlias"),
    reorderSiblings: bind("reorderMarkdownSiblings"),
  };
}

function createPdfApi(bind: BindCoreMethod): ExocortexApi["pdf"] {
  return {
    buildFileUrl: buildPdfFileUrl,
    getMetadata: bind("getPdfMetadata"),
    getPageTextBoxes: bind("getPdfPageTextBoxes"),
    searchContent: bind("searchPdfContent"),
    createBlock: bind("createBlock"),
    deleteBlock: bind("deleteBlock"),
    deleteGroup: bind("deleteGroup"),
    updateDisabledContentItems: bind("updateDisabledContentItems"),
    updateSelection: bind("updateBlockSelection"),
    previewMergeMarkdown: bind("previewMergeMarkdown"),
    mergeGroup: bind("mergeGroup"),
    updateUiState: bind("updatePdfUiState"),
  };
}

function createTaskApi(bind: BindCoreMethod): ExocortexApi["tasks"] {
  return {
    list: bind("listTasks"),
    get: bind("getTask"),
    subscribe: bind("subscribeToTaskEvents"),
  };
}

function createWorkflowApi(bind: BindCoreMethod): ExocortexApi["workflows"] {
  return {
    createTutorSession: bind("createTutorSession"),
    submitGroupDive: bind("submitGroupDive"),
    submitFlashcard: bind("submitFlashcard"),
    submitAskTutor: bind("submitAskTutor"),
    submitReTutor: bind("submitReTutor"),
    submitIntegrate: bind("submitIntegrate"),
    submitBugFinder: bind("submitBugFinder"),
    submitStudentNote: bind("submitStudentNote"),
    submitFixLatex: bind("submitFixLatex"),
    submitCompressPreview: bind("submitCompressPreview"),
    submitCompressExecute: bind("submitCompressExecute"),
    deleteQuestion: bind("deleteQuestion"),
    deleteTutorSession: bind("deleteTutorSession"),
  };
}

function looksLikeHtml(value: string): boolean {
  const trimmed = value.trim().toLowerCase();
  return trimmed.startsWith("<!doctype html") || trimmed.startsWith("<html") || trimmed.startsWith("<");
}

function extractBodyHtml(value: string): string {
  const parser = new DOMParser();
  const documentNode = parser.parseFromString(value, "text/html");
  return documentNode.body.innerHTML || value;
}

function normalizeMathMarkdown(value: string): string {
  const blockPattern = /\$\$([\s\S]*?)\$\$/g;

  return value.replace(blockPattern, (_match, mathBody: string) => {
    const normalizedLines = mathBody
      .split(/\r?\n/)
      .map((line) =>
        line
          .trim()
          .replace(/\u00A0/g, " ")
          .replace(/\u3000/g, " ")
          .replace(/\u200b/g, " ")
          .replace(/\ufeff/g, " "),
      )
      .filter((line) => line.length > 0);

    return `\n\n$$\n${normalizedLines.join("\n")}\n$$\n\n`;
  });
}

function normalizeMarkdownContent(
  path: string,
  raw: { path?: string; title?: string; html?: string; bodyHtml?: string; markdown?: string },
): MarkdownContent {
  const rawValue = raw.bodyHtml ?? raw.html ?? raw.markdown ?? "";
  const html = looksLikeHtml(rawValue)
    ? extractBodyHtml(rawValue)
    : (marked.parse(normalizeMathMarkdown(rawValue)) as string);

  return {
    path: raw.path ?? path,
    title: raw.title ?? (raw.path ?? path).split("/").filter(Boolean).at(-1) ?? path,
    html,
  };
}
