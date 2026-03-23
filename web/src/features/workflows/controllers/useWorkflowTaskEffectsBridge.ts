import { useEffect, useEffectEvent, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useExocortexApi } from "../../../app/api/ExocortexApiContext";
import { queryKeys } from "../../../app/api/exocortexApi";
import type { AssetState, MarkdownTab, MarkdownTreeNode } from "../../../app/types";
import { useAppStore } from "../../../app/store/appStore";
import type { MarkdownOpenSource } from "../../../app/store/appStore.types";
import { useTaskCenter } from "../../tasks/TaskCenterContext";
import type { TaskDetail } from "../../../generated/contracts";
import {
  documentTitleFromPath,
  findPreferredGroupMarkdownNode,
  flattenMarkdownTree,
} from "../api/helpers";
import type {
  CompressPreviewState,
  FeynmanState,
  PendingImportIntent,
} from "./types";

interface WorkflowTaskEffectsBridgeInput {
  pendingImportIntent: PendingImportIntent | null;
  setPendingImportIntent: (intent: PendingImportIntent | null) => void;
  setCompressPreview: (preview: CompressPreviewState | null) => void;
  feynman: FeynmanState | null;
  setFeynman: (next: FeynmanState | null | ((current: FeynmanState | null) => FeynmanState | null)) => void;
}

export function useWorkflowTaskEffectsBridge({
  pendingImportIntent,
  setPendingImportIntent,
  setCompressPreview,
  feynman,
  setFeynman,
}: WorkflowTaskEffectsBridgeInput): void {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
  const { tasks, tasksById } = useTaskCenter();
  const setSelectedAssetName = useAppStore((state) => state.setSelectedAssetName);
  const setAppMode = useAppStore((state) => state.setAppMode);
  const openMarkdownTab = useAppStore((state) => state.openMarkdownTab);
  const processedTaskStates = useRef<Set<string>>(new Set());
  const processingTaskStates = useRef<Set<string>>(new Set());

  const handleTerminalTask = useEffectEvent(async (task: TaskDetail) => {
    if (!isTaskReadyForEffects(task)) {
      return;
    }

    const marker = taskProcessingMarker(task);
    if (processedTaskStates.current.has(marker) || processingTaskStates.current.has(marker)) {
      return;
    }
    processingTaskStates.current.add(marker);

    try {
      if (task.kind === "asset_init") {
        await queryClient.invalidateQueries({ queryKey: queryKeys.assets });
      }
      if (task.assetName) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.assetState(task.assetName) }),
          queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(task.assetName) }),
        ]);
      }

      if (task.kind === "asset_init" && pendingImportIntent?.taskId === task.id) {
        if (task.status === "completed" && task.assetName) {
          await focusImportedAsset({
            api,
            queryClient,
            assetName: task.assetName,
            setSelectedAssetName,
            openMarkdownTab,
          });
        }
        setPendingImportIntent(null);
      }

      const artifact = latestMarkdownPath(task);
      if (task.status === "completed" && artifact && task.assetName) {
        openMarkdownTab({
          assetName: task.assetName,
          path: artifact,
          title: documentTitleFromPath(artifact),
          kind: markdownKindFromPath(artifact),
        });
      }

      if (task.kind === "compress_preview" && task.status === "completed") {
        const payload = latestPayload(task);
        if (payload && typeof payload.previewDataUrl === "string") {
          setCompressPreview({
            dataUrl: payload.previewDataUrl,
            width: typeof payload.width === "number" ? payload.width : null,
            height: typeof payload.height === "number" ? payload.height : null,
          });
        }
      }

      if (feynman?.integrateTaskId === task.id && task.status === "completed") {
        setFeynman((current) =>
          current ? { ...current, stage: "awaiting_manuscript" } : current,
        );
      }
      if (feynman?.bugFinderTaskId === task.id && task.status === "completed") {
        setFeynman((current) => (current ? { ...current, stage: "questions" } : current));
      }
      if (feynman?.studentNoteTaskId === task.id && task.status === "completed") {
        setAppMode("normal");
        setFeynman(null);
      }

      processedTaskStates.current.add(marker);
    } finally {
      processingTaskStates.current.delete(marker);
    }
  });

  useEffect(() => {
    for (const task of tasks) {
      if (task.status !== "completed" && task.status !== "failed") {
        continue;
      }
      void handleTerminalTask(tasksById[task.id] ?? task);
    }
  }, [
    handleTerminalTask,
    feynman,
    pendingImportIntent,
    tasks,
    tasksById,
  ]);
}

function latestArtifactPath(task: TaskDetail): string | null {
  const events = task.events ?? [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index]?.artifactPath) {
      return events[index].artifactPath;
    }
  }
  return null;
}

function latestPayload(task: TaskDetail): Record<string, unknown> | null {
  const events = task.events ?? [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index]?.payload) {
      return events[index].payload;
    }
  }
  return null;
}

function latestMarkdownPath(task: TaskDetail): string | null {
  const artifactPath = latestArtifactPath(task);
  if (artifactPath?.endsWith(".md")) {
    return artifactPath;
  }

  const payload = latestPayload(task);
  if (typeof payload?.markdownPath === "string" && payload.markdownPath.endsWith(".md")) {
    return payload.markdownPath;
  }
  return null;
}

function markdownKindFromPath(path: string): "ask" | "markdown" | "reference" {
  if (path.startsWith("references/")) {
    return "reference";
  }
  if (path.includes("/ask_history/")) {
    return "ask";
  }
  return "markdown";
}

function isTaskReadyForEffects(task: TaskDetail): boolean {
  if (task.kind === "compress_preview") {
    return task.status !== "completed" || latestPayload(task) !== null;
  }
  if (task.kind === "asset_init") {
    return task.status === "failed" || task.assetName !== null;
  }
  if (MARKDOWN_ARTIFACT_TASK_KINDS.has(task.kind) && task.status === "completed") {
    return task.assetName !== null && latestMarkdownPath(task) !== null;
  }
  if (latestMarkdownPath(task)) {
    return task.assetName !== null;
  }
  if (task.assetName !== null) {
    return true;
  }
  return task.status === "failed";
}

async function focusImportedAsset({
  api,
  queryClient,
  assetName,
  setSelectedAssetName,
  openMarkdownTab,
}: {
  api: ReturnType<typeof useExocortexApi>;
  queryClient: ReturnType<typeof useQueryClient>;
  assetName: string;
  setSelectedAssetName: (assetName: string | null) => void;
  openMarkdownTab: (tab: MarkdownTab, options?: { source?: MarkdownOpenSource }) => void;
}): Promise<void> {
  const [assetState, markdownTree] = await Promise.all([
    queryClient.fetchQuery({
      queryKey: queryKeys.assetState(assetName),
      queryFn: () => api.assets.getState(assetName),
    }),
    queryClient.fetchQuery({
      queryKey: queryKeys.markdownTree(assetName),
      queryFn: () => api.markdown.getTree(assetName),
    }),
  ]);

  const landingTab = resolveImportLandingTab(assetName, assetState, markdownTree);
  if (landingTab) {
    openMarkdownTab(landingTab);
    return;
  }

  setSelectedAssetName(assetName);
}

function resolveImportLandingTab(
  assetName: string,
  assetState: AssetState,
  markdownTree: MarkdownTreeNode[],
): MarkdownTab | null {
  const flatTree = flattenMarkdownTree(markdownTree).filter(
    (node): node is MarkdownTreeNode & { path: string } => typeof node.path === "string",
  );
  const initialNode = [...flatTree]
    .filter((node) => node.path.includes("/initial/"))
    .sort((left, right) => left.path.localeCompare(right.path))[0];
  if (initialNode) {
    return {
      assetName,
      path: initialNode.path,
      title: initialNode.title,
      kind: initialNode.kind,
    } as const;
  }

  const sortedGroupIdxs = [...assetState.groups]
    .map((group) => group.groupIdx)
    .sort((left, right) => left - right);
  for (const groupIdx of sortedGroupIdxs) {
    const groupNode = findPreferredGroupMarkdownNode(markdownTree, groupIdx);
    if (groupNode?.path) {
      return {
        assetName,
        path: groupNode.path,
        title: groupNode.title,
        kind: groupNode.kind,
      } as const;
    }
  }

  const stateCandidates = dedupePaths([
    assetState.uiState.currentMarkdownPath ?? null,
    ...(assetState.uiState.openMarkdownPaths ?? []),
  ]);
  for (const candidate of stateCandidates) {
    const matchingNode = flatTree.find((node) => node.path === candidate);
    if (matchingNode) {
      return {
        assetName,
        path: matchingNode.path,
        title: matchingNode.title,
        kind: matchingNode.kind,
      } as const;
    }
  }

  for (const referenceName of ["background.md", "concept.md", "formula.md"]) {
    if (!assetState.references.includes(referenceName)) {
      continue;
    }
    return {
      assetName,
      path: `references/${referenceName}`,
      title: referenceName,
      kind: "reference",
    } as const;
  }

  return null;
}

function dedupePaths(paths: Array<string | null | undefined>): string[] {
  const result: string[] = [];
  for (const path of paths) {
    if (!path || result.includes(path)) {
      continue;
    }
    result.push(path);
  }
  return result;
}

function taskProcessingMarker(task: TaskDetail): string {
  return [
    task.id,
    task.status,
    task.assetName ?? "",
    latestMarkdownPath(task) ?? "",
    task.kind === "compress_preview" && latestPayload(task) !== null ? "payload" : "",
  ].join(":");
}

const MARKDOWN_ARTIFACT_TASK_KINDS = new Set([
  "group_dive",
  "ask_tutor",
  "re_tutor",
  "integrate",
  "bug_finder",
  "student_note",
  "fix_latex",
]);
