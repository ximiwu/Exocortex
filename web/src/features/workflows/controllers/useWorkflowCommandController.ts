import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useExocortexApi } from "../../../app/api/ExocortexApiContext";
import { queryKeys } from "../../../app/api/exocortexApi";
import type { ImportAssetInput } from "../../../app/api/types";
import { useAppStore } from "../../../app/store/appStore";
import { useToasts } from "../../tasks/ToastProvider";
import { useTaskCenter } from "../../tasks/TaskCenterContext";
import {
  deriveGroupContext,
  deriveTutorContext,
  flattenMarkdownTree,
  isTutorHistoryMarkdown,
} from "../api/helpers";
import type {
  CompressPreviewState,
  ConfirmationState,
  FeynmanState,
  MarkdownContextMenuState,
  PendingImportIntent,
} from "./types";

export interface WorkflowCommandController {
  apiMode: "live" | "mock";
  selectedAssetName: string | null;
  currentMarkdownPath: string | null;
  markdownTree: ReturnType<typeof flattenMarkdownTree>;
  markdownContextMenu: MarkdownContextMenuState | null;
  questionText: string;
  tutorAskVisible: boolean;
  effectiveGroupIdx: number | null;
  effectiveTutorIdx: number | null;
  deleteQuestionEnabled: boolean;
  activeTaskPanel: boolean;
  importDialogOpen: boolean;
  importSubmitting: boolean;
  importError: string | null;
  confirmation: ConfirmationState | null;
  confirmationBusy: boolean;
  compressPreview: CompressPreviewState | null;
  pendingImportIntent: PendingImportIntent | null;
  feynman: FeynmanState | null;
  setQuestionText: (value: string) => void;
  setActiveTaskPanel: (active: boolean) => void;
  setImportDialogOpen: (open: boolean) => void;
  closeMarkdownContextMenu: () => void;
  setPendingImportIntent: (intent: PendingImportIntent | null) => void;
  setCompressPreview: (preview: CompressPreviewState | null) => void;
  setFeynman: (next: FeynmanState | null | ((current: FeynmanState | null) => FeynmanState | null)) => void;
  runMarkdownContextAction: (action: () => Promise<void>) => void;
  handleShowInfo: () => Promise<void>;
  handleShowInitial: () => Promise<void>;
  handleFixLatex: () => Promise<void>;
  handleReveal: () => Promise<void>;
  handleAskTutor: () => Promise<void>;
  openDeleteQuestionConfirmation: () => void;
  closeConfirmation: () => void;
  confirmAction: () => Promise<void>;
  handleImportSubmit: (payload: ImportAssetInput) => Promise<void>;
  closeImportDialog: () => void;
}

export function useWorkflowCommandController(): WorkflowCommandController {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
  const { pushToast } = useToasts();
  const { isGroupTaskRunning, trackSubmittedTask } = useTaskCenter();
  const selectedAssetName = useAppStore((state) => state.selectedAssetName);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const activeTaskPanel = useAppStore((state) => state.activeTaskPanel);
  const setActiveTaskPanel = useAppStore((state) => state.setActiveTaskPanel);
  const importDialogOpen = useAppStore((state) => state.importDialogOpen);
  const setImportDialogOpen = useAppStore((state) => state.setImportDialogOpen);
  const openMarkdownTab = useAppStore((state) => state.openMarkdownTab);
  const closeMarkdownTab = useAppStore((state) => state.closeMarkdownTab);
  const setSelectedAssetName = useAppStore((state) => state.setSelectedAssetName);
  const markdownContextMenuRequest = useAppStore((state) => state.markdownContextMenuRequest);
  const groupDiveRequest = useAppStore((state) => state.groupDiveRequest);
  const assetDeleteRequest = useAppStore((state) => state.assetDeleteRequest);
  const consumeMarkdownContextMenuRequest = useAppStore((state) => state.consumeMarkdownContextMenuRequest);
  const consumeGroupDiveRequest = useAppStore((state) => state.consumeGroupDiveRequest);
  const consumeAssetDeleteRequest = useAppStore((state) => state.consumeAssetDeleteRequest);
  const [importSubmitting, setImportSubmitting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [pendingImportIntent, setPendingImportIntent] = useState<PendingImportIntent | null>(null);
  const [questionText, setQuestionText] = useState("");
  const [confirmation, setConfirmation] = useState<ConfirmationState | null>(null);
  const [confirmationBusy, setConfirmationBusy] = useState(false);
  const [feynman, setFeynman] = useState<FeynmanState | null>(null);
  const [compressPreview, setCompressPreview] = useState<CompressPreviewState | null>(null);
  const [markdownContextMenu, setMarkdownContextMenu] = useState<MarkdownContextMenuState | null>(null);
  const pendingGroupDiveKeysRef = useRef<Set<string>>(new Set());

  const assetStateQuery = useQuery({
    queryKey: queryKeys.assetState(selectedAssetName),
    queryFn: () => api.assets.getState(selectedAssetName!),
    enabled: Boolean(selectedAssetName),
  });

  const markdownTreeQuery = useQuery({
    queryKey: queryKeys.markdownTree(selectedAssetName),
    queryFn: () => api.markdown.getTree(selectedAssetName!),
    enabled: Boolean(selectedAssetName),
  });

  const assetState = assetStateQuery.data ?? null;
  const markdownTree = flattenMarkdownTree(markdownTreeQuery.data ?? []);
  const groupContext = deriveGroupContext(currentMarkdownPath);
  const tutorContext = deriveTutorContext(currentMarkdownPath);
  const effectiveGroupIdx = groupContext?.groupIdx ?? assetState?.groups[0]?.groupIdx ?? null;
  const effectiveTutorIdx = tutorContext?.tutorIdx ?? null;
  const tutorAskVisible =
    selectedAssetName !== null &&
    tutorContext !== null &&
    effectiveGroupIdx !== null &&
    effectiveTutorIdx !== null;
  const deleteQuestionEnabled =
    api.capabilities.deleteQuestion && isTutorHistoryMarkdown(currentMarkdownPath);

  useEffect(() => {
    if (!markdownContextMenuRequest) {
      return;
    }

    const x = Math.max(12, Number(markdownContextMenuRequest.x ?? 0));
    const y = Math.max(12, Number(markdownContextMenuRequest.y ?? 0));
    setMarkdownContextMenu({ x, y });
    consumeMarkdownContextMenuRequest();
  }, [consumeMarkdownContextMenuRequest, markdownContextMenuRequest]);

  useEffect(() => {
    if (!groupDiveRequest) {
      return;
    }

    const assetName = typeof groupDiveRequest.assetName === "string" ? groupDiveRequest.assetName : null;
    const groupIdx = typeof groupDiveRequest.groupIdx === "number" ? groupDiveRequest.groupIdx : null;
    consumeGroupDiveRequest();
    if (!assetName || groupIdx === null) {
      return;
    }

    const groupDiveKey = `${assetName}:${groupIdx}`;
    if (
      pendingGroupDiveKeysRef.current.has(groupDiveKey) ||
      isGroupTaskRunning("group_dive", assetName, groupIdx)
    ) {
      pushToast({
        title: "Group dive already running",
        description: `Group ${groupIdx} is already in progress.`,
        tone: "warning",
      });
      return;
    }

    pendingGroupDiveKeysRef.current.add(groupDiveKey);
    void api.workflows
      .submitGroupDive({ assetName, groupIdx })
      .then((task) => {
        trackSubmittedTask(task);
      })
      .catch((error) => {
        if (error instanceof Error && error.message === "An equivalent task is already in progress.") {
          pushToast({
            title: "Group dive already running",
            description: `Group ${groupIdx} is already in progress.`,
            tone: "warning",
          });
          return;
        }
        pushToast({
          title: "Group dive failed",
          description: error instanceof Error ? error.message : "Unable to start group dive.",
          tone: "danger",
        });
      })
      .finally(() => {
        pendingGroupDiveKeysRef.current.delete(groupDiveKey);
      });
  }, [api, consumeGroupDiveRequest, groupDiveRequest, isGroupTaskRunning, pushToast, trackSubmittedTask]);

  useEffect(() => {
    if (!assetDeleteRequest) {
      return;
    }

    const assetName = typeof assetDeleteRequest.assetName === "string" ? assetDeleteRequest.assetName : null;
    consumeAssetDeleteRequest();
    if (!assetName) {
      return;
    }

    setConfirmation({
      title: "Delete Asset",
      description: `Delete ${assetName}?`,
      confirmLabel: "delete asset",
      tone: "danger",
      action: async () => {
        await api.assets.deleteAsset(assetName);
        await queryClient.invalidateQueries({ queryKey: queryKeys.assets });
        await queryClient.invalidateQueries({ queryKey: queryKeys.assetState(assetName) });
        await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(assetName) });
        if (selectedAssetName === assetName) {
          setSelectedAssetName(null);
        }
      },
    });
  }, [
    api,
    assetDeleteRequest,
    consumeAssetDeleteRequest,
    queryClient,
    selectedAssetName,
    setSelectedAssetName,
  ]);

  useEffect(() => {
    setMarkdownContextMenu(null);
  }, [currentMarkdownPath, selectedAssetName]);

  async function handleShowInfo() {
    if (!selectedAssetName) {
      return;
    }
    for (const name of ["background", "concept", "formula"]) {
      openMarkdownTab({
        assetName: selectedAssetName,
        path: `references/${name}.md`,
        title: `${name}.md`,
        kind: "reference",
      });
    }
  }

  async function handleShowInitial() {
    if (!selectedAssetName) {
      return;
    }
    const initialDocs = markdownTree.filter((node) => node.path?.includes("/initial/"));
    if (!initialDocs.length) {
      pushToast({
        title: "No initial markdown",
        description: "No initial files are available for the current asset.",
        tone: "warning",
      });
      return;
    }
    for (const node of initialDocs) {
      if (!node.path) {
        continue;
      }
      openMarkdownTab({
        assetName: selectedAssetName,
        path: node.path,
        title: node.title,
        kind: node.kind,
      });
    }
  }

  async function handleImportSubmit(payload: ImportAssetInput) {
    try {
      setImportSubmitting(true);
      setImportError(null);
      const task = await api.assets.importAsset(payload);
      trackSubmittedTask(task);
      setPendingImportIntent({
        taskId: task.id,
      });
      setImportDialogOpen(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to start asset import.";
      setImportError(message);
      pushToast({
        title: "Import failed",
        description: message,
        tone: "danger",
      });
    } finally {
      setImportSubmitting(false);
    }
  }

  async function handleFixLatex() {
    if (!selectedAssetName || !currentMarkdownPath) {
      return;
    }
    const task = await api.workflows.submitFixLatex({
      assetName: selectedAssetName,
      markdownPath: currentMarkdownPath,
    });
    trackSubmittedTask(task);
  }

  async function handleReveal() {
    if (!selectedAssetName || !currentMarkdownPath) {
      return;
    }
    await api.assets.revealAsset(selectedAssetName, currentMarkdownPath);
  }

  async function handleDeleteQuestion() {
    if (
      !selectedAssetName ||
      !currentMarkdownPath ||
      !effectiveGroupIdx ||
      !effectiveTutorIdx ||
      !api.capabilities.deleteQuestion
    ) {
      return;
    }
    await api.workflows.deleteQuestion({
      assetName: selectedAssetName,
      groupIdx: effectiveGroupIdx,
      tutorIdx: effectiveTutorIdx,
      markdownPath: currentMarkdownPath,
    });
    closeMarkdownTab(selectedAssetName, currentMarkdownPath);
    await queryClient.invalidateQueries({ queryKey: queryKeys.assetState(selectedAssetName) });
    await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(selectedAssetName) });
  }

  async function handleAskTutor() {
    if (!selectedAssetName || !effectiveGroupIdx || !questionText.trim()) {
      return;
    }

    const tutorIdx = await ensureTutorSession();
    if (!tutorIdx) {
      return;
    }

    const task = await api.workflows.submitAskTutor({
      assetName: selectedAssetName,
      groupIdx: effectiveGroupIdx,
      tutorIdx,
      question: questionText.trim(),
    });
    trackSubmittedTask(task);
    setQuestionText("");
  }

  function closeConfirmation() {
    setConfirmation(null);
  }

  async function confirmAction() {
    if (!confirmation) {
      return;
    }
    try {
      setConfirmationBusy(true);
      await confirmation.action();
      setConfirmation(null);
    } catch (error) {
      pushToast({
        title: "Action failed",
        description: error instanceof Error ? error.message : "Unable to complete the action.",
        tone: "danger",
      });
    } finally {
      setConfirmationBusy(false);
    }
  }

  function closeMarkdownContextMenu() {
    setMarkdownContextMenu(null);
  }

  function runMarkdownContextAction(action: () => Promise<void>) {
    closeMarkdownContextMenu();
    void action().catch((error) => {
      pushToast({
        title: "Action failed",
        description: error instanceof Error ? error.message : "Unable to complete the action.",
        tone: "danger",
      });
    });
  }

  function openDeleteQuestionConfirmation() {
    if (!deleteQuestionEnabled) {
      return;
    }
    setConfirmation({
      title: "Delete Question",
      description: `Delete ${currentMarkdownPath ?? "this question"}?`,
      confirmLabel: "delete question",
      tone: "danger",
      action: handleDeleteQuestion,
    });
    setMarkdownContextMenu(null);
  }

  function closeImportDialog() {
    if (importSubmitting) {
      return;
    }
    setImportError(null);
    setImportDialogOpen(false);
  }

  async function ensureTutorSession(): Promise<number | null> {
    if (!selectedAssetName || !effectiveGroupIdx) {
      return null;
    }

    if (tutorContext?.groupIdx === effectiveGroupIdx) {
      return tutorContext.tutorIdx;
    }

    pushToast({
      title: "Tutor focus unavailable",
      description: "Select text in a normal group markdown first to create a tutor focus.",
      tone: "warning",
    });
    return null;
  }

  return {
    apiMode: api.mode,
    selectedAssetName,
    currentMarkdownPath,
    markdownTree,
    markdownContextMenu,
    questionText,
    tutorAskVisible,
    effectiveGroupIdx,
    effectiveTutorIdx,
    deleteQuestionEnabled,
    activeTaskPanel,
    importDialogOpen,
    importSubmitting,
    importError,
    confirmation,
    confirmationBusy,
    compressPreview,
    pendingImportIntent,
    feynman,
    setQuestionText,
    setActiveTaskPanel,
    setImportDialogOpen,
    closeMarkdownContextMenu,
    setPendingImportIntent,
    setCompressPreview,
    setFeynman,
    runMarkdownContextAction,
    handleShowInfo,
    handleShowInitial,
    handleFixLatex,
    handleReveal,
    handleAskTutor,
    openDeleteQuestionConfirmation,
    closeConfirmation,
    confirmAction,
    handleImportSubmit,
    closeImportDialog,
  };
}
