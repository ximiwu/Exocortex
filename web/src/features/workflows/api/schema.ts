export type {
  AppMode,
  AssetState,
  AssetSummary,
  AssetUiState,
  BadgePosition,
  MarkdownTreeNode,
  Rect as BlockRect,
  TaskDetail,
  TaskEvent,
  TaskEventType,
  TaskStatus,
  TaskSummary,
  TutorSession,
} from "../../../generated/contracts";
export type {
  BugFinderTaskInput as BugFinderTaskPayload,
  ClientCapabilities,
  CompressTaskInput as CompressTaskPayload,
  CreateTutorSessionInput as CreateTutorSessionPayload,
  DeleteQuestionInput as DeleteQuestionPayload,
  FixLatexTaskInput as FixLatexTaskPayload,
  GroupTaskInput as GroupTaskPayload,
  ImportAssetInput as ImportAssetPayload,
  IntegrateTaskInput as IntegrateTaskPayload,
  TutorTaskInput as TutorTaskPayload,
} from "../../../app/api/types";
export {
  deriveGroupContext,
  deriveTutorContext,
  documentTitleFromPath,
  findGroupEnhancedMarkdownNode,
  findPreferredGroupMarkdownNode,
  flattenMarkdownTree,
  isTutorHistoryMarkdown,
} from "./helpers";

export type ApiMode = "live" | "mock";

export interface DocumentRecord {
  path: string;
  title: string;
  kind: "markdown" | "reference" | "initial" | "history" | "note";
  content: string;
}
