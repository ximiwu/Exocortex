export interface ConfirmationState {
  title: string;
  description: string;
  confirmLabel: string;
  tone?: "neutral" | "danger";
  action(): Promise<void>;
}

export interface FeynmanState {
  groupIdx: number;
  tutorIdx: number;
  stage: "integrating" | "awaiting_manuscript" | "reviewing" | "questions" | "finishing";
  integrateTaskId: string | null;
  bugFinderTaskId: string | null;
  studentNoteTaskId: string | null;
  manuscriptFiles: File[];
}

export interface PendingImportIntent {
  taskId: string;
}

export interface MarkdownContextMenuState {
  x: number;
  y: number;
}

export interface CompressPreviewState {
  dataUrl: string;
  width: number | null;
  height: number | null;
}
