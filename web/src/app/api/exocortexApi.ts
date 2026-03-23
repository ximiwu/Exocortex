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
  GroupTaskInput,
  ImportAssetInput,
  IntegrateTaskInput,
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
    createBlock(assetName: string, input: CreateBlockInput): Promise<AssetState>;
    deleteBlock(assetName: string, blockId: number): Promise<AssetState>;
    deleteGroup(assetName: string, groupIdx: number): Promise<AssetState>;
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
  markdownContent: (assetName: string | null, path: string | null) =>
    ["markdown-content", assetName, path] as const,
};

export function buildFileUrl(assetName: string): string {
  return buildClientPdfFileUrl(assetName);
}

export function buildPdfFileUrl(assetName: string): string {
  return buildClientPdfFileUrl(assetName);
}

export function createExocortexApi(options: CreateExocortexApiOptions = {}): ExocortexApi {
  return wrapCoreApi(createCoreExocortexApi(options));
}

export function wrapCoreApi(core: CoreExocortexApi): ExocortexApi {
  return {
    mode: core.mode,
    capabilities: core.capabilities,
    system: {
      getConfig: () => core.getSystemConfig(),
      updateConfig: (config) => core.updateSystemConfig(config),
    },
    assets: {
      list: () => core.listAssets(),
      getState: (assetName) => core.getAssetState(assetName),
      updateUiState: (assetName, uiState) => core.updateAssetUiState(assetName, uiState),
      importAsset: (input) => core.importAsset(input),
      deleteAsset: (assetName) => core.deleteAsset(assetName),
      revealAsset: (assetName, path) => core.revealAsset(assetName, path),
    },
    markdown: {
      getTree: (assetName) => core.getMarkdownTree(assetName),
      getContent: async (assetName, path) => normalizeMarkdownContent(path, await core.getMarkdownDocument(assetName, path)),
      getReference: (assetName, name) => core.getReference(assetName, name),
      renameNodeAlias: (input) => core.renameMarkdownNodeAlias(input),
      reorderSiblings: (input) => core.reorderMarkdownSiblings(input),
    },
    pdf: {
      buildFileUrl: (assetName) => buildPdfFileUrl(assetName),
      getMetadata: (assetName) => core.getPdfMetadata(assetName),
      getPageTextBoxes: (assetName, pageIndex) => core.getPdfPageTextBoxes(assetName, pageIndex),
      createBlock: (assetName, input) => core.createBlock(assetName, input),
      deleteBlock: (assetName, blockId) => core.deleteBlock(assetName, blockId),
      deleteGroup: (assetName, groupIdx) => core.deleteGroup(assetName, groupIdx),
      updateSelection: (assetName, mergeOrder) => core.updateBlockSelection(assetName, mergeOrder),
      previewMergeMarkdown: (assetName, blockIds) => core.previewMergeMarkdown(assetName, blockIds),
      mergeGroup: (assetName, blockIds, options) => core.mergeGroup(assetName, blockIds, options),
      updateUiState: (assetName, uiState) => core.updatePdfUiState(assetName, uiState),
    },
    tasks: {
      list: () => core.listTasks(),
      get: (taskId) => core.getTask(taskId),
      subscribe: (listener) => core.subscribeToTaskEvents(listener),
    },
    workflows: {
      createTutorSession: (input) => core.createTutorSession(input),
      submitGroupDive: (input) => core.submitGroupDive(input),
      submitAskTutor: (input) => core.submitAskTutor(input),
      submitReTutor: (input) => core.submitReTutor(input),
      submitIntegrate: (input) => core.submitIntegrate(input),
      submitBugFinder: (input) => core.submitBugFinder(input),
      submitStudentNote: (input) => core.submitStudentNote(input),
      submitFixLatex: (input) => core.submitFixLatex(input),
      submitCompressPreview: (input) => core.submitCompressPreview(input),
      submitCompressExecute: (input) => core.submitCompressExecute(input),
      deleteQuestion: (input) => core.deleteQuestion(input),
      deleteTutorSession: (input) => core.deleteTutorSession(input),
    },
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

function normalizeMarkdownContent(
  path: string,
  raw: { path?: string; title?: string; html?: string; bodyHtml?: string; markdown?: string },
): MarkdownContent {
  const rawValue = raw.bodyHtml ?? raw.html ?? raw.markdown ?? "";
  const html = looksLikeHtml(rawValue) ? extractBodyHtml(rawValue) : (marked.parse(rawValue) as string);

  return {
    path: raw.path ?? path,
    title: raw.title ?? (raw.path ?? path).split("/").filter(Boolean).at(-1) ?? path,
    html,
  };
}
