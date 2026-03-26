import type { ExocortexApi } from "./client";
import type {
  AppSystemConfig,
  AppSystemConfigUpdate,
  AssetState,
  AssetSummary,
  BlockRect,
  BugFinderTaskPayload,
  ClientCapabilities,
  CompressTaskPayload,
  CreateTutorSessionPayload,
  DeleteQuestionPayload,
  DeleteTutorSessionInput,
  FlashcardTaskPayload,
  GroupTaskPayload,
  ImportAssetPayload,
  MarkdownTreeNode,
  PdfPageTextBoxes,
  PdfSearchResponse,
  PreviewMergeMarkdownResponse,
  TaskDetail,
  TaskEvent,
  TaskSummary,
  TutorSession,
  TutorTaskPayload,
  IntegrateTaskPayload,
  FixLatexTaskPayload,
} from "./schema";
import type { MarkdownContentPayload, PdfMetadata, Rect } from "../../../generated/contracts";

interface MockAssetRecord {
  summary: AssetSummary;
  state: AssetState;
  tree: MarkdownTreeNode[];
  documents: Record<string, string>;
  references: Record<string, string>;
  contentListEntries: MockContentListEntry[];
}

type TaskListener = (event: TaskEvent) => void;

interface MockContentListEntry {
  page_idx: number;
  x: number;
  y: number;
  width: number;
  height: number;
  type?: string;
  text?: string;
  text_level?: number;
  list_items?: string[];
  img_path?: string;
  image_explaination?: string;
  image_caption?: string[];
  image_footnote?: string[];
  table_caption?: string[];
  table_body?: string;
  table_footnote?: string[];
  sub_type?: string;
  code_caption?: string[];
  code_body?: string;
  guess_lang?: string;
  text_format?: string;
}

export function createMockExocortexClient(): ExocortexApi {
  return createMockExocortexApi();
}

export function createMockExocortexApi(): ExocortexApi {
  return new MockExocortexClient();
}

class MockExocortexClient implements ExocortexApi {
  readonly mode = "mock" as const;

  readonly capabilities: ClientCapabilities = {
    deleteQuestion: true,
    deleteTutorSession: true,
  };

  private readonly assets = new Map<string, MockAssetRecord>();
  private readonly tasks = new Map<string, TaskDetail>();
  private readonly listeners = new Set<TaskListener>();
  private systemConfig: AppSystemConfig = {
    themeMode: "light",
    sidebarTextLineClamp: 1,
    sidebarFontSizePx: 14,
    tutorReasoningEffort: "medium",
    tutorWithGlobalContext: true,
  };

  constructor() {
    for (const record of createSeedAssets()) {
      this.assets.set(record.summary.name, record);
    }
  }

  async listAssets(): Promise<AssetSummary[]> {
    return Array.from(this.assets.values())
      .map((record) => deepClone(record.summary))
      .sort((left, right) => left.name.localeCompare(right.name));
  }

  async getAssetState(assetName: string): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    return deepClone(asset.state);
  }

  async getMarkdownTree(assetName: string): Promise<MarkdownTreeNode[]> {
    const asset = this.requireAsset(assetName);
    return deepClone(asset.tree);
  }

  async getMarkdownContent(assetName: string, path: string): Promise<string> {
    const asset = this.requireAsset(assetName);
    const content = asset.documents[path];
    if (!content) {
      throw new Error(`Markdown not found: ${path}`);
    }

    return content;
  }

  async getMarkdownDocument(assetName: string, path: string): Promise<MarkdownContentPayload> {
    const html = await this.getMarkdownContent(assetName, path);
    return {
      path,
      title: path.split("/").filter(Boolean).at(-1) ?? path,
      markdown: "",
      html,
      bodyHtml: html,
      headHtml: "",
    };
  }

  async getReference(assetName: string, name: string): Promise<string> {
    const asset = this.requireAsset(assetName);
    const content = asset.references[name];
    if (!content) {
      throw new Error(`Reference not found: ${name}`);
    }

    return content;
  }

  async getSystemConfig(): Promise<AppSystemConfig> {
    return deepClone(this.systemConfig);
  }

  async updateSystemConfig(config: AppSystemConfigUpdate): Promise<AppSystemConfig> {
    this.systemConfig = {
      themeMode:
        config.themeMode === undefined
          ? this.systemConfig.themeMode
          : config.themeMode === "dark"
            ? "dark"
            : "light",
      sidebarTextLineClamp:
        config.sidebarTextLineClamp === undefined
          ? this.systemConfig.sidebarTextLineClamp
          : Math.max(1, Math.min(6, Math.floor(config.sidebarTextLineClamp))),
      sidebarFontSizePx:
        config.sidebarFontSizePx === undefined
          ? this.systemConfig.sidebarFontSizePx
          : Math.max(10, Math.min(24, Math.floor(config.sidebarFontSizePx))),
      tutorReasoningEffort:
        config.tutorReasoningEffort === undefined
          ? this.systemConfig.tutorReasoningEffort
          : config.tutorReasoningEffort,
      tutorWithGlobalContext:
        config.tutorWithGlobalContext === undefined
          ? this.systemConfig.tutorWithGlobalContext
          : config.tutorWithGlobalContext,
    };
    return deepClone(this.systemConfig);
  }

  async updateAssetUiState(assetName: string, uiState: Partial<AssetState["uiState"]>): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    asset.state.uiState = {
      ...asset.state.uiState,
      ...uiState,
    };
    return deepClone(asset.state);
  }

  async createTutorSession(payload: CreateTutorSessionPayload): Promise<TutorSession> {
    const asset = this.requireAsset(payload.assetName);
    const tutorIdx = nextTutorIndex(asset, payload.groupIdx);
    ensureTutorNode(asset, payload.groupIdx, tutorIdx);
    asset.documents[`group_data/${payload.groupIdx}/tutor_data/${tutorIdx}/focus.md`] =
      payload.focusMarkdown.trim() || "# Tutor Focus\n\nThe imported tutor session started here.";
    const markdownPath = `group_data/${payload.groupIdx}/tutor_data/${tutorIdx}/focus.md`;
    asset.state.uiState.currentMarkdownPath = markdownPath;
    return {
      tutorIdx,
      markdownPath,
    };
  }

  async importAsset(payload: ImportAssetPayload): Promise<TaskSummary> {
    const assetName = [payload.assetSubfolder.trim(), payload.assetName.trim()]
      .filter(Boolean)
      .join("/");

    return this.queueTask({
      kind: "asset_init",
      title: `Import asset: ${assetName || payload.assetName}`,
      assetName: assetName || payload.assetName,
      run: (taskId) => {
        this.emit(taskId, "started", "Upload received. Preparing asset...");
        this.emit(taskId, "log", `Reading ${payload.sourceFile.name}`);
        this.emit(taskId, "log", `Reading ${payload.markdownFile.name}`);
        this.emit(taskId, "log", `Storing ${payload.contentListFile.name} as content_list.json`);
        this.emit(taskId, "progress", "Preparing PDF and markdown assets...", 0.35);
        this.emit(taskId, "progress", "Running extractors...", 0.72);
        const record = createImportedAssetRecord(
          assetName || payload.assetName,
          payload.sourceFile.name
        );
        this.assets.set(record.summary.name, record);
        this.emit(taskId, "completed", `Asset ${record.summary.name} is ready.`, 1, record.summary.name);
      }
    });
  }

  async deleteAsset(assetName: string): Promise<void> {
    this.requireAsset(assetName);
    this.assets.delete(assetName);
  }

  async revealAsset(assetName: string, path?: string | null): Promise<void> {
    const asset = this.requireAsset(assetName);
    if (path && !hasRevealTarget(asset, path)) {
      if (/^group_data\/\d+\/flashcard\/apkg\/?$/i.test(path)) {
        return;
      }
      throw new Error(`Path not found: ${path}`);
    }
  }

  async getPdfMetadata(assetName: string): Promise<PdfMetadata> {
    const asset = this.requireAsset(assetName);
    return {
      pageCount: asset.state.asset.pageCount,
      referenceDpi: 130,
      defaultDpi: 130,
      minDpi: 72,
      maxDpi: 1200,
      pageSizes: Array.from({ length: asset.state.asset.pageCount }, () => ({
        width: 1024,
        height: 1448,
      })),
    };
  }

  async getPdfPageTextBoxes(assetName: string, pageIndex: number): Promise<PdfPageTextBoxes> {
    const asset = this.requireAsset(assetName);
    return {
      pageIndex,
      items: asset.contentListEntries
        .filter((entry) => entry.page_idx === pageIndex + 1)
        .map((entry) => ({
          itemIndex: asset.contentListEntries.indexOf(entry) + 1,
          pageIndex,
          fractionRect: {
            x: entry.x,
            y: entry.y,
            width: entry.width,
            height: entry.height,
          },
        })),
    };
  }

  async searchPdfContent(assetName: string, query: string): Promise<PdfSearchResponse> {
    const asset = this.requireAsset(assetName);
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      return {
        query: "",
        matches: [],
      };
    }

    const disabledContentItemIndexes = new Set(asset.state.disabledContentItemIndexes);
    const normalizedQueryLower = normalizedQuery.toLowerCase();
    const matches = asset.contentListEntries
      .flatMap((entry, index) => {
        const itemIndex = index + 1;
        if (disabledContentItemIndexes.has(itemIndex)) {
          return [];
        }

        const markdown = renderContentListEntry(entry, itemIndex);
        if (!markdown.trim()) {
          return [];
        }
        if (!markdown.toLowerCase().includes(normalizedQueryLower)) {
          return [];
        }

        return [
          {
            itemIndex,
            pageIndex: entry.page_idx - 1,
            fractionRect: {
              x: entry.x,
              y: entry.y,
              width: entry.width,
              height: entry.height,
            },
          },
        ];
      });

    return {
      query: normalizedQuery,
      matches,
    };
  }

  buildPdfFileUrl(assetName: string): string {
    return `/api/assets/${encodeURIComponent(assetName)}/pdf/file`;
  }

  async createBlock(assetName: string, input: { pageIndex: number; fractionRect: Rect }): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    const blockId = asset.state.nextBlockId;
    asset.state.blocks.push({
      blockId,
      pageIndex: input.pageIndex,
      fractionRect: input.fractionRect,
      groupIdx: null,
    });
    asset.state.mergeOrder = [...asset.state.mergeOrder.filter((candidate) => candidate !== blockId), blockId];
    asset.state.nextBlockId += 1;
    this.syncAssetSummary(asset);
    return deepClone(asset.state);
  }

  async deleteBlock(assetName: string, blockId: number): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    const target = asset.state.blocks.find((block) => block.blockId === blockId) ?? null;
    asset.state.blocks = asset.state.blocks.filter((block) => block.blockId !== blockId);
    asset.state.mergeOrder = asset.state.mergeOrder.filter((candidate) => candidate !== blockId);
    if (target?.groupIdx !== null) {
      asset.state.groups = asset.state.groups
        .map((group) => ({
          ...group,
          blockIds: group.blockIds.filter((candidate) => candidate !== blockId),
        }))
        .filter((group) => group.blockIds.length > 0);
    }
    this.syncAssetSummary(asset);
    return deepClone(asset.state);
  }

  async deleteGroup(assetName: string, groupIdx: number): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    const removed = new Set(
      asset.state.groups.find((group) => group.groupIdx === groupIdx)?.blockIds ?? [],
    );
    asset.state.groups = asset.state.groups.filter((group) => group.groupIdx !== groupIdx);
    asset.state.blocks = asset.state.blocks.filter((block) => !removed.has(block.blockId));
    asset.state.mergeOrder = asset.state.mergeOrder.filter((blockId) => !removed.has(blockId));
    this.syncAssetSummary(asset);
    return deepClone(asset.state);
  }

  async updateDisabledContentItems(assetName: string, disabledContentItemIndexes: number[]): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    asset.state.disabledContentItemIndexes = Array.from(
      new Set(
        disabledContentItemIndexes
          .map((value) => Number(value))
          .filter((value) => Number.isInteger(value) && value > 0),
      ),
    ).sort((left, right) => left - right);
    return deepClone(asset.state);
  }

  async updateBlockSelection(assetName: string, mergeOrder: number[]): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    asset.state.mergeOrder = Array.from(new Set(mergeOrder));
    return deepClone(asset.state);
  }

  async previewMergeMarkdown(assetName: string, blockIds: number[]): Promise<PreviewMergeMarkdownResponse> {
    const asset = this.requireAsset(assetName);
    const selectedBlocks = resolvePreviewBlocks(asset, blockIds);
    const disabledContentItemIndexes = new Set(asset.state.disabledContentItemIndexes);
    const warnings: string[] = [];
    const markdown = asset.contentListEntries
      .flatMap((entry, index) =>
        !disabledContentItemIndexes.has(index + 1) &&
        selectedBlocks.some(
          (block) =>
            block.pageIndex + 1 === entry.page_idx &&
            rectFullyContainsRect(block.fractionRect, {
              x: entry.x,
              y: entry.y,
              width: entry.width,
              height: entry.height,
            }),
        )
          ? [{ entry, itemIndex: index + 1 }]
          : [],
      )
      .map(({ entry, itemIndex }) => renderContentListEntry(entry, itemIndex, warnings))
      .filter((fragment) => fragment.trim().length > 0)
      .join("\n\n");

    return { markdown, warning: warnings.length ? Array.from(new Set(warnings)).join("\n") : null };
  }

  async mergeGroup(
    assetName: string,
    blockIds: number[],
    options: { markdownContent?: string | null; groupIdx?: number | null } = {},
  ): Promise<AssetState> {
    const asset = this.requireAsset(assetName);
    const nextGroupIdx =
      options.groupIdx ??
      Math.max(0, ...asset.state.groups.map((group) => group.groupIdx)) + 1;
    const selected = new Set(blockIds);
    asset.state.blocks = asset.state.blocks.map((block) =>
      selected.has(block.blockId) ? { ...block, groupIdx: nextGroupIdx } : block,
    );
    asset.state.groups = [
      ...asset.state.groups.filter((group) => group.groupIdx !== nextGroupIdx),
      { groupIdx: nextGroupIdx, blockIds: Array.from(selected) },
    ];
    asset.state.mergeOrder = [];
    if (options.markdownContent) {
      asset.documents[`group_data/${nextGroupIdx}/content.md`] = options.markdownContent;
    }
    this.syncAssetSummary(asset);
    return deepClone(asset.state);
  }

  async updatePdfUiState(assetName: string, uiState: AssetState["uiState"]): Promise<AssetState> {
    return this.updateAssetUiState(assetName, uiState);
  }

  async listTasks(): Promise<TaskSummary[]> {
    return Array.from(this.tasks.values())
      .map((task) => toTaskSummary(task))
      .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  }

  async getTask(taskId: string): Promise<TaskDetail> {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task not found: ${taskId}`);
    }

    return deepClone(task);
  }

  subscribeToTaskEvents(listener: TaskListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  async submitGroupDive(payload: GroupTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "group_dive",
      title: `Group dive: group ${payload.groupIdx}`,
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const path = `group_data/${payload.groupIdx}/img_explainer_data/enhanced.md`;
        ensureGroupDocument(
          asset,
          payload.groupIdx,
          path,
          `# Group ${payload.groupIdx} Enhanced\n\nMock explainer output is ready for review.`
        );
        asset.state.uiState.currentMarkdownPath = path;
        this.emit(taskId, "started", `Running explainer for group ${payload.groupIdx}...`);
        this.emit(taskId, "log", "Gathering group images and existing notes.");
        this.emit(taskId, "progress", "Drafting enhanced explanation...", 0.54);
        this.emit(taskId, "artifact", "Enhanced markdown available.", null, path);
        this.emit(taskId, "completed", `Group ${payload.groupIdx} enhanced.md updated.`, 1, path);
      }
    });
  }

  async submitFlashcard(payload: FlashcardTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "flashcard",
      title: `Flashcard: group ${payload.groupIdx}`,
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const flashcardPath = `group_data/${payload.groupIdx}/flashcard/md/card-1.md`;
        const flashcardHtmlFrontPath = `group_data/${payload.groupIdx}/flashcard/html/card-1.front.html`;
        const flashcardHtmlBackPath = `group_data/${payload.groupIdx}/flashcard/html/card-1.back.html`;
        const flashcardApkgPath = `group_data/${payload.groupIdx}/flashcard/apkg/deck.apkg`;
        asset.documents[flashcardPath] =
          "question:\nWhat is the key takeaway?\nanswer:\nA mock flashcard generated from enhanced.md.";
        asset.documents[flashcardHtmlFrontPath] = "<!DOCTYPE html><html><body><p>What is the key takeaway?</p></body></html>";
        asset.documents[flashcardHtmlBackPath] =
          "<!DOCTYPE html><html><body><p>A mock flashcard generated from enhanced.md.</p></body></html>";
        asset.documents[flashcardApkgPath] = "mock apkg";
        ensureGroupOtherMarkdownPath(asset, payload.groupIdx, flashcardPath);
        this.emit(taskId, "started", `Generating flashcards for group ${payload.groupIdx}...`);
        this.emit(taskId, "log", "Gathering enhanced.md and ask_history references.");
        this.emit(taskId, "completed", "Flashcards saved.", 1, `group_data/${payload.groupIdx}/flashcard/md`);
      }
    });
  }

  async submitAskTutor(payload: TutorTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "ask_tutor",
      title: `Ask Tutor: group ${payload.groupIdx}`,
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const tutorRoot = `group_data/${payload.groupIdx}/tutor_data/${payload.tutorIdx}`;
        const answerPath = `${tutorRoot}/answer.md`;
        const historyPath = `${tutorRoot}/ask_history/${nextHistoryIndex(asset, tutorRoot)}.md`;
        ensureTutorNode(asset, payload.groupIdx, payload.tutorIdx);
        asset.documents[answerPath] =
          `# Tutor Answer\n\nQuestion:\n\n> ${payload.question}\n\nAnswer:\n\nThis is a mock tutor response grounded in the selected group.`;
        asset.documents[historyPath] = `# Ask History\n\n${payload.question}`;
        upsertTutorChild(asset, payload.groupIdx, payload.tutorIdx, {
          id: `tutor:${payload.groupIdx}:${payload.tutorIdx}:answer`,
          kind: "markdown",
          title: "answer.md",
          path: answerPath,
          children: []
        });
        upsertTutorChild(asset, payload.groupIdx, payload.tutorIdx, {
          id: `tutor:${payload.groupIdx}:${payload.tutorIdx}:history:${historyPath.split("/").at(-1)?.replace(".md", "") ?? "1"}`,
          kind: "ask",
          title: historyPath.split("/").at(-1) ?? "history.md",
          path: historyPath,
          children: []
        });
        asset.state.uiState.currentMarkdownPath = historyPath;
        this.emit(taskId, "started", "Sending question to tutor...");
        this.emit(taskId, "log", payload.question);
        this.emit(taskId, "progress", "Synthesizing answer...", 0.62);
        this.emit(taskId, "completed", "Tutor response saved.", 1, historyPath);
      }
    });
  }

  async submitReTutor(payload: TutorTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "re_tutor",
      title: `Re-tutor: group ${payload.groupIdx}`,
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const bugPath = `group_data/${payload.groupIdx}/tutor_data/${payload.tutorIdx}/bugs.md`;
        ensureTutorNode(asset, payload.groupIdx, payload.tutorIdx);
        asset.documents[bugPath] =
          `# Bug Review Follow-up\n\nQuestion:\n\n> ${payload.question}\n\nResolution:\n\nThe mock re-tutor flow added a clarification for the deduction gap.`;
        upsertTutorChild(asset, payload.groupIdx, payload.tutorIdx, {
          id: `tutor:${payload.groupIdx}:${payload.tutorIdx}:bugs`,
          kind: "markdown",
          title: "bugs.md",
          path: bugPath,
          children: []
        });
        asset.state.uiState.currentMarkdownPath = bugPath;
        this.emit(taskId, "started", "Sending follow-up question...");
        this.emit(taskId, "log", payload.question);
        this.emit(taskId, "completed", "Re-tutor answer saved.", 1, bugPath);
      }
    });
  }

  async submitIntegrate(payload: IntegrateTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "integrate",
      title: `Start Feynman: group ${payload.groupIdx}`,
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const notePath = `group_data/${payload.groupIdx}/tutor_data/${payload.tutorIdx}/note.md`;
        ensureTutorNode(asset, payload.groupIdx, payload.tutorIdx);
        asset.documents[notePath] =
          "# Feynman Note\n\nUse this note as the hidden scaffold while you derive the explanation yourself.";
        upsertTutorChild(asset, payload.groupIdx, payload.tutorIdx, {
          id: `tutor:${payload.groupIdx}:${payload.tutorIdx}:note`,
          kind: "markdown",
          title: "note.md",
          path: notePath,
          children: []
        });
        this.emit(taskId, "started", "Preparing note.md for Feynman mode...");
        this.emit(taskId, "progress", "Locking in tutor context...", 0.45);
        this.emit(taskId, "completed", "Feynman note ready.", 1, notePath);
      }
    });
  }

  async submitBugFinder(payload: BugFinderTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "bug_finder",
      title: `Bug review: group ${payload.groupIdx}`,
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const bugPath = `group_data/${payload.groupIdx}/tutor_data/${payload.tutorIdx}/bugs.md`;
        ensureTutorNode(asset, payload.groupIdx, payload.tutorIdx);
        asset.documents[bugPath] =
          `# Bug Review\n\nUploaded manuscript images: ${payload.manuscriptFiles.length}\n\n- Missing justification in the middle derivation.\n- Final sign convention needs a short explanation.\n- One symbol should be defined before the result statement.`;
        upsertTutorChild(asset, payload.groupIdx, payload.tutorIdx, {
          id: `tutor:${payload.groupIdx}:${payload.tutorIdx}:bugs`,
          kind: "markdown",
          title: "bugs.md",
          path: bugPath,
          children: []
        });
        asset.state.uiState.currentMarkdownPath = bugPath;
        this.emit(taskId, "started", "Reviewing deduction images...");
        this.emit(taskId, "log", `Received ${payload.manuscriptFiles.length} manuscript image(s).`);
        this.emit(taskId, "progress", "Comparing manuscript against note.md...", 0.68);
        this.emit(taskId, "completed", "Bug review ready.", 1, bugPath);
      }
    });
  }

  async submitStudentNote(payload: IntegrateTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "student_note",
      title: `Finish improvement: group ${payload.groupIdx}`,
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const path = `group_data/${payload.groupIdx}/img_explainer_data/enhanced.md`;
        ensureGroupDocument(
          asset,
          payload.groupIdx,
          path,
          `# Group ${payload.groupIdx} Enhanced\n\nThe improvement flow has merged the student's final explanation back into enhanced.md.`
        );
        asset.state.uiState.currentMarkdownPath = path;
        this.emit(taskId, "started", "Writing student note back into enhanced.md...");
        this.emit(taskId, "completed", "Student note saved.", 1, path);
      }
    });
  }

  async submitFixLatex(payload: FixLatexTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "fix_latex",
      title: "Fix latex",
      assetName: payload.assetName,
      run: (taskId) => {
        const asset = this.requireAsset(payload.assetName);
        const existing = asset.documents[payload.markdownPath];
        if (!existing) {
          throw new Error(`Markdown not found: ${payload.markdownPath}`);
        }
        asset.documents[payload.markdownPath] =
          `${existing}\n\n<!-- mock latex fixer applied -->`;
        this.emit(taskId, "started", "Applying latex fixes...");
        this.emit(taskId, "completed", "Latex fix completed.", 1, payload.markdownPath);
      }
    });
  }

  async submitCompressPreview(payload: CompressTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "compress_preview",
      title: `Compress preview: ${payload.assetName}`,
      assetName: payload.assetName,
      run: (taskId) => {
        this.emit(taskId, "started", "Rendering compressed preview...");
        this.emit(taskId, "progress", compressPreviewMessage(payload), 0.5);
        this.emit(
          taskId,
          "completed",
          "Compressed preview ready.",
          1,
          `${payload.assetName}/compressed_preview.pdf`
        );
      }
    });
  }

  async submitCompressExecute(payload: CompressTaskPayload): Promise<TaskSummary> {
    return this.queueTask({
      kind: "compress_execute",
      title: `Compress execute: ${payload.assetName}`,
      assetName: payload.assetName,
      run: (taskId) => {
        this.emit(taskId, "started", "Writing compressed PDF...");
        this.emit(taskId, "progress", compressPreviewMessage(payload), 0.5);
        this.emit(
          taskId,
          "completed",
          "Compressed PDF saved into raw.pdf.",
          1,
          `${payload.assetName}/raw.pdf`
        );
      }
    });
  }

  async renameMarkdownNodeAlias(payload: {
    assetName: string;
    nodeId: string;
    path?: string | null;
    alias: string;
  }): Promise<{ nodeId: string; path: string | null; title: string }> {
    const asset = this.requireAsset(payload.assetName);
    const node = findNodeById(asset.tree, payload.nodeId);
    if (!node) {
      throw new Error(`Node not found: ${payload.nodeId}`);
    }
    if (node.kind === "folder" || (node.children.length > 0 && node.kind !== "group" && node.kind !== "tutor")) {
      throw new Error(`Node cannot be renamed: ${payload.nodeId}`);
    }
    if (node.path && payload.path && node.path !== payload.path) {
      throw new Error(`Path mismatch: ${payload.nodeId}`);
    }
    const title = defaultMockNodeTitle(node, payload.alias.trim());
    node.title = title;
    return {
      nodeId: node.id,
      path: node.path,
      title
    };
  }

  async reorderMarkdownSiblings(payload: {
    assetName: string;
    parentId?: string | null;
    orderedNodeIds: string[];
  }): Promise<{ parentId: string | null; orderedNodeIds: string[] }> {
    const asset = this.requireAsset(payload.assetName);
    const siblings = payload.parentId ? findNodeById(asset.tree, payload.parentId)?.children ?? null : asset.tree;
    if (!siblings) {
      throw new Error(`Parent not found: ${payload.parentId}`);
    }
    const siblingIds = siblings.map((node) => node.id);
    if (
      payload.orderedNodeIds.length !== siblingIds.length ||
      new Set(payload.orderedNodeIds).size !== payload.orderedNodeIds.length ||
      payload.orderedNodeIds.some((id) => !siblingIds.includes(id))
    ) {
      throw new Error("orderedNodeIds must be a complete sibling permutation.");
    }
    const byId = new Map(siblings.map((node) => [node.id, node]));
    const reordered = payload.orderedNodeIds.map((id) => byId.get(id)!).filter(Boolean);
    siblings.splice(0, siblings.length, ...reordered);
    return {
      parentId: payload.parentId ?? null,
      orderedNodeIds: payload.orderedNodeIds
    };
  }

  async deleteQuestion(payload: DeleteQuestionPayload): Promise<void> {
    const asset = this.requireAsset(payload.assetName);
    delete asset.documents[payload.markdownPath];
    asset.tree = removeTreePath(asset.tree, payload.markdownPath);
  }

  async deleteTutorSession(payload: DeleteTutorSessionInput): Promise<void> {
    const asset = this.requireAsset(payload.assetName);
    const prefix = `group_data/${payload.groupIdx}/tutor_data/${payload.tutorIdx}/`;
    for (const path of Object.keys(asset.documents)) {
      if (path.startsWith(prefix)) {
        delete asset.documents[path];
      }
    }

    asset.tree = removeTutorNode(asset.tree, payload.groupIdx, payload.tutorIdx);
  }

  private async queueTask(config: {
    kind: string;
    title: string;
    assetName: string | null;
    run: (taskId: string) => void;
  }): Promise<TaskSummary> {
    const createdAt = new Date().toISOString();
    const taskId = `task_${crypto.randomUUID()}`;
    const queuedEvent = createTaskEvent({
      taskId,
      kind: config.kind,
      assetName: config.assetName,
      status: "queued",
      eventType: "queued",
      message: "Task queued.",
      progress: null,
      artifactPath: null
    });
    const detail: TaskDetail = {
      id: taskId,
      kind: config.kind,
      status: "queued",
      title: config.title,
      assetName: config.assetName,
      createdAt,
      updatedAt: createdAt,
      events: [queuedEvent]
    };
    this.tasks.set(taskId, detail);
    this.broadcast(queuedEvent);

    window.setTimeout(() => {
      try {
        config.run(taskId);
      } catch (error) {
        this.emit(
          taskId,
          "failed",
          error instanceof Error ? error.message : "Mock task failed."
        );
      }
    }, 180);

    return toTaskSummary(detail);
  }

  private emit(
    taskId: string,
    eventType: TaskEvent["eventType"],
    message: string,
    progress: number | null = null,
    artifactPath: string | null = null
  ): void {
    const task = this.tasks.get(taskId);
    if (!task) {
      return;
    }

    const status = eventType === "completed"
      ? "completed"
      : eventType === "failed"
        ? "failed"
        : eventType === "queued"
          ? "queued"
          : "running";
    const event = createTaskEvent({
      taskId,
      kind: task.kind,
      assetName: task.assetName,
      status,
      eventType,
      message,
      progress,
      artifactPath
    });
    task.status = status;
    task.updatedAt = event.timestamp;
    task.events = [...task.events, event];
    this.tasks.set(taskId, task);
    this.broadcast(event);
  }

  private broadcast(event: TaskEvent): void {
    for (const listener of this.listeners) {
      listener(deepClone(event));
    }
  }

  private requireAsset(assetName: string): MockAssetRecord {
    const asset = this.assets.get(assetName);
    if (!asset) {
      throw new Error(`Asset not found: ${assetName}`);
    }
    return asset;
  }

  private syncAssetSummary(asset: MockAssetRecord): void {
    asset.summary = {
      ...asset.summary,
      hasBlocks: asset.state.blocks.length > 0,
      pageCount: asset.state.asset.pageCount,
    };
  }
}

function createSeedAssets(): MockAssetRecord[] {
  return [
    createAssetRecord("physics/paper_1", 12),
    createAssetRecord("math/notes_demo", 8)
  ];
}

function createAssetRecord(assetName: string, pageCount: number): MockAssetRecord {
  const documents: Record<string, string> = {
    "group_data/1/img_explainer_data/enhanced.md":
      "# Group 1 Enhanced\n\nThis group explains the central derivation and anchors the workflow demo.",
    "group_data/1/img_explainer_data/initial/1.md":
      "# Initial 1\n\nInitial chunk for group 1.",
    "group_data/1/img_explainer_data/initial/2.md":
      "# Initial 2\n\nSecond initial chunk for group 1.",
    "group_data/1/tutor_data/1/focus.md":
      "# Tutor Focus\n\nWhy does the conservation argument introduce a boundary term?",
    "group_data/1/tutor_data/1/answer.md":
      "# Tutor Answer\n\nBecause the chosen region has a non-zero flux contribution across its boundary.",
    "group_data/1/tutor_data/1/ask_history/1.md":
      "# Ask History 1\n\nExplain the boundary term again in simpler language.",
    "group_data/2/img_explainer_data/enhanced.md":
      "# Group 2 Enhanced\n\nThis group collects the follow-up observations for the appendix.",
    "group_data/2/img_explainer_data/initial/1.md":
      "# Initial 1\n\nStarting point for group 2."
  };

  const tree: MarkdownTreeNode[] = [
    {
      id: "group:1",
      kind: "group",
      title: "Group 1",
      path: "group_data/1/img_explainer_data/enhanced.md",
      children: [
        {
          id: "tutor:1:1:focus",
          kind: "tutor",
          title: "focus.md",
          path: "group_data/1/tutor_data/1/focus.md",
          children: [
            {
              id: "tutor:1:1:answer",
              kind: "markdown",
              title: "answer.md",
              path: "group_data/1/tutor_data/1/answer.md",
              children: []
            },
            {
              id: "tutor:1:1:history:1",
              kind: "ask",
              title: "1.md",
              path: "group_data/1/tutor_data/1/ask_history/1.md",
              children: []
            }
          ]
        },
        {
          id: "group:1:other",
          kind: "folder",
          title: "Other",
          path: null,
          children: [
            {
              id: "group:1:other/img_explainer_data/initial",
              kind: "folder",
              title: "initial",
              path: null,
              children: [
                {
                  id: "group:1:other/img_explainer_data/initial:1.md",
                  kind: "markdown",
                  title: "1.md",
                  path: "group_data/1/img_explainer_data/initial/1.md",
                  children: []
                },
                {
                  id: "group:1:other/img_explainer_data/initial:2.md",
                  kind: "markdown",
                  title: "2.md",
                  path: "group_data/1/img_explainer_data/initial/2.md",
                  children: []
                }
              ]
            }
          ]
        }
      ]
    },
    {
      id: "group:2",
      kind: "group",
      title: "Group 2",
      path: "group_data/2/img_explainer_data/enhanced.md",
      children: [
        {
          id: "group:2:other",
          kind: "folder",
          title: "Other",
          path: null,
          children: [
            {
              id: "group:2:other/img_explainer_data/initial",
              kind: "folder",
              title: "initial",
              path: null,
              children: [
                {
                  id: "group:2:other/img_explainer_data/initial:1.md",
                  kind: "markdown",
                  title: "1.md",
                  path: "group_data/2/img_explainer_data/initial/1.md",
                  children: []
                }
              ]
            }
          ]
        }
      ]
    }
  ];

  const state: AssetState = {
    asset: {
      name: assetName,
      pageCount,
      pdfPath: `${assetName}/raw.pdf`
    },
    references: ["background.md", "concept.md", "formula.md"],
    blocks: [
      {
        blockId: 1,
        pageIndex: 0,
        fractionRect: {
          x: 100 / 1024,
          y: 130 / 1448,
          width: 280 / 1024,
          height: 120 / 1448,
        },
        groupIdx: 1
      },
      {
        blockId: 2,
        pageIndex: 1,
        fractionRect: {
          x: 120 / 1024,
          y: 220 / 1448,
          width: 310 / 1024,
          height: 140 / 1448,
        },
        groupIdx: 2
      }
    ],
    mergeOrder: [1, 2],
    disabledContentItemIndexes: [],
    nextBlockId: 3,
    groups: [
      { groupIdx: 1, blockIds: [1] },
      { groupIdx: 2, blockIds: [2] }
    ],
    uiState: {
      currentPage: 1,
      zoom: 1,
      pdfScrollFraction: 0,
      pdfScrollLeftFraction: 0,
      currentMarkdownPath: "group_data/1/img_explainer_data/enhanced.md",
      openMarkdownPaths: ["group_data/1/img_explainer_data/enhanced.md"],
      sidebarCollapsed: false,
      sidebarCollapsedNodeIds: [],
      markdownScrollFractions: {},
      sidebarWidthRatio: 180 / 960,
      rightRailWidthRatio: 340 / 960,
    }
  };

  const contentListEntries: MockContentListEntry[] = [
    {
      page_idx: 1,
      type: "text",
      text: "Mock heading",
      text_level: 2,
      x: 0.14,
      y: 0.11,
      width: 0.18,
      height: 0.05,
    },
    {
      page_idx: 1,
      type: "text",
      text: "Mock paragraph for auto merge preview.",
      x: 0.16,
      y: 0.18,
      width: 0.2,
      height: 0.06,
    },
    {
      page_idx: 1,
      type: "list",
      list_items: ["first point", "second point"],
      x: 0.18,
      y: 0.26,
      width: 0.2,
      height: 0.06,
    },
    {
      page_idx: 1,
      type: "image",
      img_path: "images/mock-figure.png",
      image_explaination: "Mock figure explanation.",
      image_caption: ["Figure 1"],
      image_footnote: ["Mock source"],
      x: 0.2,
      y: 0.34,
      width: 0.18,
      height: 0.07,
    },
    {
      page_idx: 2,
      type: "table",
      table_caption: ["Table 1"],
      table_body: "<table><tr><td>demo</td></tr></table>",
      table_footnote: ["Mock table footnote"],
      x: 0.14,
      y: 0.17,
      width: 0.2,
      height: 0.08,
    },
    {
      page_idx: 2,
      type: "code",
      sub_type: "code",
      code_caption: ["Listing 1"],
      code_body: "print('mock')",
      guess_lang: "python",
      x: 0.18,
      y: 0.29,
      width: 0.18,
      height: 0.08,
    },
  ];

  return {
    summary: {
      name: assetName,
      pageCount,
      hasReferences: true,
      hasBlocks: true
    },
    state,
    tree,
    documents,
    references: {
      background: "# Background\n\nMock background context for the selected asset.",
      concept: "# Concept\n\nCore concept notes generated by the extractor.",
      formula: "# Formula\n\nImportant formulas and definitions."
    },
    contentListEntries,
  };
}

function createImportedAssetRecord(assetName: string, sourceName: string): MockAssetRecord {
  const record = createAssetRecord(assetName, 6);
  record.documents["group_data/1/img_explainer_data/enhanced.md"] =
    `# Imported Asset\n\nSource file: **${sourceName}**\n\nThis asset was created through the browser upload flow.`;
  record.summary.name = assetName;
  record.state.asset.name = assetName;
  record.state.asset.pdfPath = `${assetName}/raw.pdf`;
  record.tree[0]!.path = "group_data/1/img_explainer_data/enhanced.md";
  record.state.uiState.currentMarkdownPath = "group_data/1/img_explainer_data/enhanced.md";
  record.state.uiState.openMarkdownPaths = ["group_data/1/img_explainer_data/enhanced.md"];
  return record;
}

function ensureGroupDocument(
  asset: MockAssetRecord,
  groupIdx: number,
  path: string,
  content: string
): void {
  asset.documents[path] = content;
  asset.tree = asset.tree.map((node) =>
    node.id === `group:${groupIdx}`
      ? {
          ...node,
          path
        }
      : node
  );
}

function hasRevealTarget(asset: MockAssetRecord, path: string): boolean {
  if (asset.documents[path]) {
    return true;
  }
  if (asset.references[path.replace(/^references\//, "")]) {
    return true;
  }
  const normalized = path.replace(/\/+$/, "");
  return Object.keys(asset.documents).some((candidate) => candidate.startsWith(`${normalized}/`));
}

function ensureGroupOtherMarkdownPath(
  asset: MockAssetRecord,
  groupIdx: number,
  path: string,
): void {
  const groupNode = asset.tree.find((node) => node.id === `group:${groupIdx}`);
  if (!groupNode) {
    return;
  }

  let otherNode = groupNode.children.find((node) => node.id === `group:${groupIdx}:other`) ?? null;
  if (!otherNode) {
    otherNode = {
      id: `group:${groupIdx}:other`,
      kind: "folder",
      title: "Other",
      path: null,
      children: [],
    };
    groupNode.children = [...groupNode.children, otherNode];
  }

  const relative = path.replace(`group_data/${groupIdx}/`, "");
  const parts = relative.split("/").filter(Boolean);
  const fileName = parts.pop();
  if (!fileName) {
    return;
  }

  let parent = otherNode;
  let parentId = otherNode.id;
  for (const part of parts) {
    const folderId = `${parentId}/${part}`;
    let folderNode = parent.children.find((child) => child.id === folderId) ?? null;
    if (!folderNode) {
      folderNode = {
        id: folderId,
        kind: "folder",
        title: part,
        path: null,
        children: [],
      };
      parent.children = [...parent.children, folderNode].sort((left, right) =>
        left.title.localeCompare(right.title, undefined, { numeric: true }),
      );
    }
    parent = folderNode;
    parentId = folderId;
  }

  const leafId = `${parentId}:${fileName}`;
  const leafNode: MarkdownTreeNode = {
    id: leafId,
    kind: "markdown",
    title: fileName,
    path,
    children: [],
  };
  const nextChildren = parent.children.filter((child) => child.id !== leafId && child.path !== path);
  parent.children = [...nextChildren, leafNode].sort((left, right) =>
    left.title.localeCompare(right.title, undefined, { numeric: true }),
  );
}

function ensureTutorNode(
  asset: MockAssetRecord,
  groupIdx: number,
  tutorIdx: number
): void {
  const tutorNodeId = `tutor:${groupIdx}:${tutorIdx}:focus`;
  const tutorPath = `group_data/${groupIdx}/tutor_data/${tutorIdx}/focus.md`;
  const groupNode = asset.tree.find((node) => node.id === `group:${groupIdx}`);
  if (!groupNode) {
    return;
  }

  const existing = groupNode.children.find((node) => node.id === tutorNodeId);
  if (existing) {
    return;
  }

  groupNode.children = [
    ...groupNode.children,
    {
      id: tutorNodeId,
      kind: "tutor",
      title: "focus.md",
      path: tutorPath,
      children: []
    }
  ];

  asset.documents[tutorPath] =
    "# Tutor Focus\n\nThe imported tutor session started here.";
}

function upsertTutorChild(
  asset: MockAssetRecord,
  groupIdx: number,
  tutorIdx: number,
  node: MarkdownTreeNode
): void {
  const tutorNode = findTutorNode(asset.tree, groupIdx, tutorIdx);
  if (!tutorNode) {
    return;
  }

  const nextChildren = tutorNode.children.filter((child) => child.path !== node.path && child.id !== node.id);
  tutorNode.children = [...nextChildren, node];
  tutorNode.children.sort((left, right) => left.title.localeCompare(right.title, undefined, { numeric: true }));
}

function findTutorNode(
  tree: MarkdownTreeNode[],
  groupIdx: number,
  tutorIdx: number
): MarkdownTreeNode | null {
  const groupNode = tree.find((node) => node.id === `group:${groupIdx}`);
  if (!groupNode) {
    return null;
  }

  return groupNode.children.find((node) => node.id === `tutor:${groupIdx}:${tutorIdx}:focus`) ?? null;
}

function findNodeById(tree: MarkdownTreeNode[], nodeId: string): MarkdownTreeNode | null {
  for (const node of tree) {
    if (node.id === nodeId) {
      return node;
    }
    const child = findNodeById(node.children, nodeId);
    if (child) {
      return child;
    }
  }
  return null;
}

function defaultMockNodeTitle(node: MarkdownTreeNode, alias: string): string {
  if (alias) {
    return alias;
  }
  if (node.kind === "group") {
    const match = node.id.match(/^group:(\d+)$/);
    return match ? `Group ${match[1]}` : node.title;
  }
  return node.path?.split("/").filter(Boolean).at(-1) ?? node.title;
}

function removeTreePath(tree: MarkdownTreeNode[], path: string): MarkdownTreeNode[] {
  return tree
    .filter((node) => node.path !== path)
    .map((node) => ({
      ...node,
      children: removeTreePath(node.children, path)
    }));
}

function removeTutorNode(tree: MarkdownTreeNode[], groupIdx: number, tutorIdx: number): MarkdownTreeNode[] {
  const tutorId = `tutor:${groupIdx}:${tutorIdx}:focus`;
  return tree.map((node) => {
    if (node.id === `group:${groupIdx}`) {
      return {
        ...node,
        children: node.children.filter((child) => child.id !== tutorId),
      };
    }

    return {
      ...node,
      children: removeTutorNode(node.children, groupIdx, tutorIdx),
    };
  });
}

function nextHistoryIndex(asset: MockAssetRecord, tutorRoot: string): number {
  const prefix = `${tutorRoot}/ask_history/`;
  const indices = Object.keys(asset.documents)
    .filter((path) => path.startsWith(prefix))
    .map((path) => Number(path.replace(prefix, "").replace(".md", "")))
    .filter((value) => Number.isFinite(value));
  return (indices.length ? Math.max(...indices) : 0) + 1;
}

function nextTutorIndex(asset: MockAssetRecord, groupIdx: number): number {
  const prefix = `group_data/${groupIdx}/tutor_data/`;
  const indices = Object.keys(asset.documents)
    .filter((path) => path.startsWith(prefix))
    .map((path) => Number(path.replace(prefix, "").split("/")[0]))
    .filter((value) => Number.isFinite(value));
  return (indices.length ? Math.max(...indices) : 0) + 1;
}

function resolvePreviewBlocks(asset: MockAssetRecord, blockIds: number[]) {
  if (!blockIds.length) {
    throw new Error("Select one or more blocks before generating markdown.");
  }

  const blockMap = new Map(asset.state.blocks.map((block) => [block.blockId, block]));
  const resolved: AssetState["blocks"] = [];
  const seen = new Set<number>();
  for (const rawBlockId of blockIds) {
    const blockId = Number(rawBlockId);
    const block = blockMap.get(blockId);
    if (!block) {
      throw new Error(`Block ${blockId} not found.`);
    }
    if (block.groupIdx != null) {
      throw new Error(`Block ${blockId} is already grouped.`);
    }
    if (seen.has(blockId)) {
      continue;
    }
    seen.add(blockId);
    resolved.push(block);
  }
  return resolved;
}

function rectFullyContainsRect(container: Rect, candidate: Rect, epsilon = 1e-6): boolean {
  const containerRight = container.x + container.width;
  const containerBottom = container.y + container.height;
  const candidateRight = candidate.x + candidate.width;
  const candidateBottom = candidate.y + candidate.height;

  return (
    candidate.x >= container.x - epsilon &&
    candidate.y >= container.y - epsilon &&
    candidateRight <= containerRight + epsilon &&
    candidateBottom <= containerBottom + epsilon
  );
}

function renderContentListEntry(entry: MockContentListEntry, itemIndex?: number, warnings?: string[]): string {
  const entryType = normalizeEntryType(entry.type);
  const textFormat = normalizeEntryType(entry.text_format);

  if (entryType === "list") {
    return joinNonEmpty(entry.list_items ?? [], "  \n");
  }
  if (entryType === "image") {
    let body = (entry.image_explaination ?? "").trim();
    if (!body) {
      body = entry.img_path ? `![](${entry.img_path})` : "";
      warnings?.push(
        `Image item${itemIndex != null ? ` ${itemIndex}` : ""} is missing image_explaination. The markdown preview fell back to img_path.`,
      );
    }
    const captions = joinNonEmpty(entry.image_caption ?? [], "  \n");
    const footnotes = joinNonEmpty(entry.image_footnote ?? [], "  \n");
    return footnotes ? joinNonEmpty([captions, body, footnotes], "  \n") : joinNonEmpty([body, captions], "  \n");
  }
  if (entryType === "table") {
    const captions = joinNonEmpty(entry.table_caption ?? [], "  \n");
    const footnotes = joinNonEmpty(entry.table_footnote ?? [], "  \n");
    const body = (entry.table_body ?? "").trim() || (entry.img_path ? `![](${entry.img_path})` : "");
    return joinNonEmpty([captions, body, footnotes], "\n");
  }
  if (entryType === "code" || normalizeEntryType(entry.sub_type) === "code") {
    const captions = joinNonEmpty(entry.code_caption ?? [], "  \n");
    const body = (entry.code_body ?? "").trim();
    const guessLang = (entry.guess_lang ?? "").trim();
    const fenced = body ? `\`\`\`${guessLang}\n${body}\n\`\`\`` : "";
    return joinNonEmpty([captions, fenced], "  \n");
  }
  if (entryType === "algorithm" || normalizeEntryType(entry.sub_type) === "algorithm") {
    const captions = joinNonEmpty(entry.code_caption ?? [], "  \n");
    return joinNonEmpty([captions, (entry.code_body ?? "").trim()], "  \n");
  }
  if (entryType === "equation" || entryType === "interline_equation" || textFormat === "latex") {
    return (entry.text ?? "").trim();
  }
  if ((entry.text ?? "").trim()) {
    const titleLevel = typeof entry.text_level === "number" ? Math.max(1, Math.min(4, Math.round(entry.text_level))) : null;
    return titleLevel ? `${"#".repeat(titleLevel)} ${entry.text!.trim()}` : entry.text!.trim();
  }
  return "";
}

function joinNonEmpty(parts: Array<string | undefined | null>, separator: string): string {
  return parts.map((part) => (part ?? "").trim()).filter(Boolean).join(separator);
}

function normalizeEntryType(value: string | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function compressPreviewMessage(payload: CompressTaskPayload): string {
  const rect = rectLabel(payload.fractionRect);
  return `ratio=${payload.ratio}, scale=${payload.compressScale.toFixed(2)}, rect=${rect}, badge=${payload.drawBadge ? payload.badgePosition : "off"}`;
}

function rectLabel(rect: BlockRect): string {
  return `${rect.x.toFixed(2)},${rect.y.toFixed(2)},${rect.width.toFixed(2)},${rect.height.toFixed(2)}`;
}

function createTaskEvent(args: {
  taskId: string;
  kind: string;
  assetName: string | null;
  status: TaskSummary["status"];
  eventType: TaskEvent["eventType"];
  message: string;
  progress: number | null;
  artifactPath: string | null;
}): TaskEvent {
  return {
    taskId: args.taskId,
    kind: args.kind,
    assetName: args.assetName,
    status: args.status,
    eventType: args.eventType,
    message: args.message,
    progress: args.progress,
    artifactPath: args.artifactPath,
    payload: null,
    timestamp: new Date().toISOString()
  };
}

function toTaskSummary(task: TaskDetail): TaskSummary {
  return {
    id: task.id,
    kind: task.kind,
    status: task.status,
    title: task.title,
    assetName: task.assetName,
    createdAt: task.createdAt,
    updatedAt: task.updatedAt
  };
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
