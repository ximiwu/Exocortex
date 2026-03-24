import type { components, operations } from "./openapi";

export type ApiSource = "live" | "mock";
export type ThemeMode = "light" | "dark";
export type AppMode = "normal" | "compress" | "feynman";
export type TaskStatus = "queued" | "running" | "completed" | "failed";
export type TaskEventType =
  | "queued"
  | "started"
  | "progress"
  | "log"
  | "artifact"
  | "completed"
  | "failed";
export type BadgePosition = "top_left" | "top_right" | "bottom_left" | "bottom_right";
type SuccessStatusCode = 200 | 201 | 202;

type OperationRequestContent<TOperation extends keyof operations> =
  operations[TOperation] extends { requestBody: { content: infer TContent } } ? TContent : never;

type OperationResponses<TOperation extends keyof operations> =
  operations[TOperation] extends { responses: infer TResponses } ? TResponses : never;

export type JsonOperationRequest<TOperation extends keyof operations> =
  OperationRequestContent<TOperation> extends { "application/json": infer TBody } ? TBody : never;

export type MultipartOperationRequest<TOperation extends keyof operations> =
  OperationRequestContent<TOperation> extends { "multipart/form-data": infer TBody } ? TBody : never;

export type JsonOperationSuccessResponse<TOperation extends keyof operations> =
  Extract<keyof OperationResponses<TOperation>, SuccessStatusCode> extends infer TSuccess
    ? TSuccess extends keyof OperationResponses<TOperation>
      ? OperationResponses<TOperation>[TSuccess] extends {
          content: { "application/json": infer TBody };
        }
        ? TBody
        : never
      : never
    : never;

export type Rect = components["schemas"]["RectModel"];
export type Size = components["schemas"]["SizeModel"];
export type AssetSummary = components["schemas"]["AssetSummaryModel"];
type AssetStateWire = components["schemas"]["AssetStateModel"];
type AssetUiStateWire = NonNullable<AssetStateWire["uiState"]>;
type AssetBlockWire = NonNullable<AssetStateWire["blocks"]>[number];
type AssetGroupWire = NonNullable<AssetStateWire["groups"]>[number];
type MarkdownTreeNodeWire = components["schemas"]["MarkdownTreeNodeModel"];
type PdfMetadataWire = components["schemas"]["PdfMetadataModel"];
export type MarkdownContentPayload = components["schemas"]["MarkdownContentModel"];
export type TutorSession = components["schemas"]["TutorSessionModel"];
export type CreateBlockRequest = components["schemas"]["CreateBlockRequest"];
export type MergeGroupRequest = components["schemas"]["MergeGroupRequest"];
export type UpdateDisabledContentItemsRequest = components["schemas"]["UpdateDisabledContentItemsRequest"];
export type UpdateUiStateRequest = components["schemas"]["UpdateUiStateRequest"];
export type CreateTutorRequest = components["schemas"]["CreateTutorRequest"];
export type UpdateMarkdownNodeAliasRequest = components["schemas"]["UpdateMarkdownNodeAliasRequest"];
export type ReorderMarkdownSiblingsRequest = components["schemas"]["ReorderMarkdownSiblingsRequest"];
export type GroupWorkflowRequest = components["schemas"]["GroupWorkflowRequest"];
export type TutorWorkflowRequest = components["schemas"]["TutorWorkflowRequest"];
export type AskTutorWorkflowRequest = components["schemas"]["AskTutorWorkflowRequest"];
export type ReTutorWorkflowRequest = components["schemas"]["ReTutorWorkflowRequest"];
export type FixLatexWorkflowRequest = components["schemas"]["FixLatexWorkflowRequest"];
export type CompressTaskRequest = components["schemas"]["CompressTaskRequest"];
export type ImportAssetFormRequest = components["schemas"]["Body_import_asset_api_assets_import_post"];
export type AssetInitFormRequest = components["schemas"]["Body_submit_asset_init_api_tasks_asset_init_post"];
export type BugFinderFormRequest = components["schemas"]["Body_submit_bug_finder_api_tasks_bug_finder_post"];
export type MessageResponse = components["schemas"]["MessageResponse"];
export type HttpValidationError = components["schemas"]["HTTPValidationError"];
export type ValidationError = components["schemas"]["ValidationError"];
export type AssetRootResponse = components["schemas"]["AssetRootResponse"];
type TaskSummaryWire = components["schemas"]["TaskSummaryModel"];
type TaskEventWire = components["schemas"]["TaskEventModel"];
type TaskDetailWire = components["schemas"]["TaskDetailModel"];

export type ImportAssetRequestBody = MultipartOperationRequest<"import_asset_api_assets_import_post">;
export type ImportAssetResponse = JsonOperationSuccessResponse<"import_asset_api_assets_import_post">;

export type CreateTutorSessionRequest = JsonOperationRequest<
  "create_tutor_session_api_assets__asset_name__groups__group_idx__tutors_post"
>;
export type CreateTutorSessionResponse = JsonOperationSuccessResponse<
  "create_tutor_session_api_assets__asset_name__groups__group_idx__tutors_post"
>;

export type UpdateMarkdownNodeAliasRequestBody = JsonOperationRequest<
  "update_markdown_node_alias_api_assets__asset_name__markdown_nodes_alias_patch"
>;
export type UpdateMarkdownNodeAliasResponse = JsonOperationSuccessResponse<
  "update_markdown_node_alias_api_assets__asset_name__markdown_nodes_alias_patch"
>;

export type ReorderMarkdownSiblingsRequestBody = JsonOperationRequest<
  "reorder_markdown_siblings_api_assets__asset_name__markdown_nodes_reorder_post"
>;
export type ReorderMarkdownSiblingsResponse = JsonOperationSuccessResponse<
  "reorder_markdown_siblings_api_assets__asset_name__markdown_nodes_reorder_post"
>;

export type SubmitAssetInitRequestBody = MultipartOperationRequest<"submit_asset_init_api_tasks_asset_init_post">;
export type SubmitAssetInitResponse = JsonOperationSuccessResponse<"submit_asset_init_api_tasks_asset_init_post">;

export type SubmitGroupDiveRequest = JsonOperationRequest<"submit_group_dive_api_tasks_group_dive_post">;
export type SubmitGroupDiveResponse = JsonOperationSuccessResponse<"submit_group_dive_api_tasks_group_dive_post">;

export type SubmitAskTutorRequest = JsonOperationRequest<"submit_ask_tutor_api_tasks_ask_tutor_post">;
export type SubmitAskTutorResponse = JsonOperationSuccessResponse<"submit_ask_tutor_api_tasks_ask_tutor_post">;

export type SubmitReTutorRequest = JsonOperationRequest<"submit_re_tutor_api_tasks_re_tutor_post">;
export type SubmitReTutorResponse = JsonOperationSuccessResponse<"submit_re_tutor_api_tasks_re_tutor_post">;

export type SubmitIntegrateRequest = JsonOperationRequest<"submit_integrate_api_tasks_integrate_post">;
export type SubmitIntegrateResponse = JsonOperationSuccessResponse<"submit_integrate_api_tasks_integrate_post">;

export type SubmitStudentNoteRequest = JsonOperationRequest<"submit_student_note_api_tasks_student_note_post">;
export type SubmitStudentNoteResponse = JsonOperationSuccessResponse<"submit_student_note_api_tasks_student_note_post">;

export type SubmitFixLatexRequest = JsonOperationRequest<"submit_fix_latex_api_tasks_fix_latex_post">;
export type SubmitFixLatexResponse = JsonOperationSuccessResponse<"submit_fix_latex_api_tasks_fix_latex_post">;

export type SubmitCompressPreviewRequest = JsonOperationRequest<"submit_compress_preview_api_tasks_compress_preview_post">;
export type SubmitCompressPreviewResponse = JsonOperationSuccessResponse<
  "submit_compress_preview_api_tasks_compress_preview_post"
>;

export type SubmitCompressExecuteRequest = JsonOperationRequest<"submit_compress_execute_api_tasks_compress_execute_post">;
export type SubmitCompressExecuteResponse = JsonOperationSuccessResponse<
  "submit_compress_execute_api_tasks_compress_execute_post"
>;

export type SubmitBugFinderRequestBody = MultipartOperationRequest<"submit_bug_finder_api_tasks_bug_finder_post">;
export type SubmitBugFinderResponse = JsonOperationSuccessResponse<"submit_bug_finder_api_tasks_bug_finder_post">;

export interface AssetUiState
  extends Omit<
    AssetUiStateWire,
    "currentMarkdownPath" | "openMarkdownPaths" | "sidebarCollapsedNodeIds" | "markdownScrollFractions"
  > {
  currentMarkdownPath: string | null;
  openMarkdownPaths: string[];
  sidebarCollapsedNodeIds: string[];
  markdownScrollFractions: Record<string, number>;
}

export interface AssetBlock extends Omit<AssetBlockWire, "groupIdx"> {
  groupIdx: number | null;
}

export interface AssetGroup extends Omit<AssetGroupWire, "blockIds"> {
  blockIds: number[];
}

export interface AssetState
  extends Omit<AssetStateWire, "references" | "blocks" | "mergeOrder" | "groups" | "uiState"> {
  references: string[];
  blocks: AssetBlock[];
  mergeOrder: number[];
  disabledContentItemIndexes: number[];
  groups: AssetGroup[];
  uiState: AssetUiState;
}

export interface MarkdownTreeNode extends Omit<MarkdownTreeNodeWire, "path" | "children"> {
  path: string | null;
  children: MarkdownTreeNode[];
}

export interface PdfMetadata extends PdfMetadataWire {
  referenceDpi?: number;
}

export interface TaskSummary extends Omit<TaskSummaryWire, "status" | "assetName"> {
  status: TaskStatus;
  assetName: string | null;
}

export interface TaskEvent
  extends Omit<TaskEventWire, "status" | "eventType" | "progress" | "artifactPath" | "payload"> {
  status: TaskStatus;
  eventType: TaskEventType;
  progress: number | null;
  artifactPath: string | null;
  payload: Record<string, unknown> | null;
}

export interface TaskDetail
  extends Omit<TaskDetailWire, "status" | "events" | "latestEvent" | "result" | "assetName"> {
  status: TaskStatus;
  events: TaskEvent[];
  assetName: string | null;
  latestEvent?: TaskEvent | null;
  result?: Record<string, unknown> | null;
}

export interface ApiEnvelope<T> {
  data: T;
  source: ApiSource;
}

export interface MarkdownContent {
  path: string;
  title: string;
  html: string;
}

export interface MarkdownTab {
  assetName: string;
  path: string;
  title: string;
  kind: string;
}
