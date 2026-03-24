import type {
  AskTutorWorkflowRequest,
  CompressTaskRequest,
  CreateTutorRequest,
  FixLatexWorkflowRequest,
  GroupWorkflowRequest,
  Rect,
  ReorderMarkdownSiblingsRequest,
  ReTutorWorkflowRequest,
  ThemeMode,
  TutorWorkflowRequest,
  UpdateMarkdownNodeAliasRequest,
} from "../../generated/contracts";

export interface ClientCapabilities {
  deleteQuestion: boolean;
  deleteTutorSession: boolean;
}

export interface ImportAssetInput {
  sourceFile: File;
  markdownFile: File;
  contentListFile: File;
  assetName: string;
  assetSubfolder: string;
}

export interface BugFinderTaskInput extends TutorWorkflowRequest {
  manuscriptFiles: File[];
}

export interface DeleteQuestionInput extends TutorWorkflowRequest {
  markdownPath: string;
}

export type DeleteTutorSessionInput = TutorWorkflowRequest;

export interface AppSystemConfig {
  themeMode: ThemeMode;
  sidebarTextLineClamp: number;
  sidebarFontSizePx: number;
  tutorReasoningEffort: TutorReasoningEffort;
  tutorWithGlobalContext: boolean;
}

export type TutorReasoningEffort = "low" | "medium" | "high" | "xhigh";

export interface AppSystemConfigUpdate {
  themeMode?: ThemeMode;
  sidebarTextLineClamp?: number;
  sidebarFontSizePx?: number;
  tutorReasoningEffort?: TutorReasoningEffort;
  tutorWithGlobalContext?: boolean;
}

export interface CreateTutorSessionInput extends CreateTutorRequest {
  assetName: string;
  groupIdx: number;
}

export interface RenameMarkdownNodeAliasInput extends UpdateMarkdownNodeAliasRequest {
  assetName: string;
}

export interface ReorderMarkdownSiblingsInput extends ReorderMarkdownSiblingsRequest {
  assetName: string;
  orderedNodeIds: string[];
}

export interface CreateBlockInput {
  pageIndex: number;
  fractionRect: Rect;
}

export interface PdfTextBox {
  itemIndex: number;
  pageIndex: number;
  fractionRect: Rect;
}

export interface PdfPageTextBoxes {
  pageIndex: number;
  items: PdfTextBox[];
}

export interface PdfSearchMatch {
  itemIndex: number;
  pageIndex: number;
  fractionRect: Rect;
}

export interface PdfSearchResponse {
  query: string;
  matches: PdfSearchMatch[];
}

export interface MergeGroupInput {
  markdownContent?: string | null;
  groupIdx?: number | null;
}

export interface PreviewMergeMarkdownResponse {
  markdown: string;
  warning?: string | null;
}

export type GroupTaskInput = GroupWorkflowRequest;
export type TutorTaskInput = AskTutorWorkflowRequest;
export type ReTutorTaskInput = ReTutorWorkflowRequest;
export type IntegrateTaskInput = TutorWorkflowRequest;
export interface FixLatexTaskInput extends FixLatexWorkflowRequest {
  assetName: string;
}
export type CompressTaskInput = CompressTaskRequest;
