import type {
  AskTutorWorkflowRequest,
  CompressTaskRequest,
  CreateTutorRequest,
  FixLatexWorkflowRequest,
  GroupWorkflowRequest,
  Rect,
  ReorderMarkdownSiblingsRequest,
  ReTutorWorkflowRequest,
  TutorWorkflowRequest,
  UpdateMarkdownNodeAliasRequest,
} from "../../generated/contracts";

export interface ClientCapabilities {
  deleteQuestion: boolean;
}

export interface ImportAssetInput {
  sourceFile: File;
  assetName: string;
  assetSubfolder: string;
  skipImg2MdMarkdownFile: File | null;
  compressEnabled: boolean;
}

export interface BugFinderTaskInput extends TutorWorkflowRequest {
  manuscriptFiles: File[];
}

export interface DeleteQuestionInput extends TutorWorkflowRequest {
  markdownPath: string;
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
  rect: Rect;
}

export interface MergeGroupInput {
  markdownContent?: string | null;
  groupIdx?: number | null;
}

export type GroupTaskInput = GroupWorkflowRequest;
export type TutorTaskInput = AskTutorWorkflowRequest;
export type ReTutorTaskInput = ReTutorWorkflowRequest;
export type IntegrateTaskInput = TutorWorkflowRequest;
export interface FixLatexTaskInput extends FixLatexWorkflowRequest {
  assetName: string;
}
export type CompressTaskInput = CompressTaskRequest;
