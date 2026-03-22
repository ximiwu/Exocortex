import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import type { ImportAssetInput } from "../../app/api/types";
import { SHELL_SLOT_IDS } from "../../app/shellSlots";
import { useAppStore } from "../../app/store/appStore";
import { TaskCenter } from "../tasks/TaskCenter";
import { useTaskCenter } from "../tasks/TaskCenterContext";
import { useToasts } from "../tasks/ToastProvider";
import {
  deriveGroupContext,
  deriveTutorContext,
  flattenMarkdownTree,
  isTutorHistoryMarkdown
} from "./api/helpers";
import { AssetImportDialog } from "./AssetImportDialog";
import { ConfirmationDialog } from "./ConfirmationDialog";

interface ConfirmationState {
  title: string;
  description: string;
  confirmLabel: string;
  tone?: "neutral" | "danger";
  action(): Promise<void>;
}

interface FeynmanState {
  groupIdx: number;
  tutorIdx: number;
  stage: "integrating" | "awaiting_manuscript" | "reviewing" | "questions" | "finishing";
  integrateTaskId: string | null;
  bugFinderTaskId: string | null;
  studentNoteTaskId: string | null;
  manuscriptFiles: File[];
}

interface PendingImportIntent {
  taskId: string;
  enterCompressMode: boolean;
}

interface MarkdownContextMenuState {
  x: number;
  y: number;
}

export function WorkflowBridge() {
  const api = useExocortexApi();
  const tutorBody = useSlotElement(SHELL_SLOT_IDS.tutorPanel);
  const queryClient = useQueryClient();
  const { tasks, tasksById, isTaskRunning } = useTaskCenter();
  const { pushToast } = useToasts();
  const selectedAssetName = useAppStore((state) => state.selectedAssetName);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const activeTaskPanel = useAppStore((state) => state.activeTaskPanel);
  const setActiveTaskPanel = useAppStore((state) => state.setActiveTaskPanel);
  const setAppMode = useAppStore((state) => state.setAppMode);
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
  const [compressPreview, setCompressPreview] = useState<{
    dataUrl: string;
    width: number | null;
    height: number | null;
  } | null>(null);
  const [markdownContextMenu, setMarkdownContextMenu] = useState<MarkdownContextMenuState | null>(null);
  const processedTaskStates = useRef<Set<string>>(new Set());

  const assetStateQuery = useQuery({
    queryKey: queryKeys.assetState(selectedAssetName),
    queryFn: () => api.assets.getState(selectedAssetName!),
    enabled: Boolean(selectedAssetName)
  });

  const markdownTreeQuery = useQuery({
    queryKey: queryKeys.markdownTree(selectedAssetName),
    queryFn: () => api.markdown.getTree(selectedAssetName!),
    enabled: Boolean(selectedAssetName)
  });

  const assetState = assetStateQuery.data ?? null;
  const markdownTree = markdownTreeQuery.data ?? [];
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
    const closeMenu = () => {
      setMarkdownContextMenu(null);
    };

    window.addEventListener("click", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("keydown", closeMenu);
    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("keydown", closeMenu);
    };
  }, []);

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

    void api.workflows
      .submitGroupDive({ assetName, groupIdx })
      .then(() => {
        setActiveTaskPanel(true);
      })
      .catch((error) => {
        pushToast({
          title: "Group dive failed",
          description: error instanceof Error ? error.message : "Unable to start group dive.",
          tone: "danger"
        });
      });
  }, [api, consumeGroupDiveRequest, groupDiveRequest, pushToast, setActiveTaskPanel]);

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
      }
    });
  }, [api, assetDeleteRequest, consumeAssetDeleteRequest, queryClient, selectedAssetName, setSelectedAssetName]);

  useEffect(() => {
    setMarkdownContextMenu(null);
  }, [currentMarkdownPath, selectedAssetName]);

  useEffect(() => {
    for (const task of tasks) {
      if (task.status !== "completed" && task.status !== "failed") {
        continue;
      }

      const marker = `${task.id}:${task.status}`;
      if (processedTaskStates.current.has(marker)) {
        continue;
      }
      processedTaskStates.current.add(marker);

      if (task.kind === "asset_init") {
        void queryClient.invalidateQueries({ queryKey: queryKeys.assets });
      }
      if (task.assetName) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.assetState(task.assetName) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(task.assetName) });
      }
      if (task.kind === "asset_init" && pendingImportIntent?.taskId === task.id) {
        setPendingImportIntent(null);
        if (pendingImportIntent.enterCompressMode && task.status === "completed" && task.assetName) {
          setSelectedAssetName(task.assetName);
          setAppMode("compress");
          pushToast({
            title: "Compress mode ready",
            description: "Import finished. Drag on the PDF pane to define the shared compress region.",
            tone: "success"
          });
        }
      }

      const artifact = latestArtifactPath(tasksById[task.id]?.events ?? []);
      if (task.status === "completed" && artifact?.endsWith(".md") && task.assetName) {
        openMarkdownTab({
          assetName: task.assetName,
          path: artifact,
          title: artifact.split("/").filter(Boolean).at(-1) ?? artifact,
          kind: "markdown"
        });
      }

      if (task.kind === "compress_preview" && task.status === "completed") {
        const payload = latestPayload(tasksById[task.id]?.events ?? []);
        if (payload && typeof payload.previewDataUrl === "string") {
          setCompressPreview({
            dataUrl: payload.previewDataUrl,
            width: typeof payload.width === "number" ? payload.width : null,
            height: typeof payload.height === "number" ? payload.height : null
          });
        }
      }

      if (feynman?.integrateTaskId === task.id && task.status === "completed") {
        setFeynman((current) =>
          current ? { ...current, stage: "awaiting_manuscript" } : current
        );
      }
      if (feynman?.bugFinderTaskId === task.id && task.status === "completed") {
        setFeynman((current) => (current ? { ...current, stage: "questions" } : current));
      }
      if (feynman?.studentNoteTaskId === task.id && task.status === "completed") {
        setAppMode("normal");
        setFeynman(null);
      }
    }
  }, [
    feynman,
    openMarkdownTab,
    pendingImportIntent,
    pushToast,
    queryClient,
    setAppMode,
    setSelectedAssetName,
    tasks,
    tasksById
  ]);

  return (
    <>
      {markdownContextMenu ? (
        <div
          className="markdown-contextMenu"
          style={{ left: `${markdownContextMenu.x}px`, top: `${markdownContextMenu.y}px` }}
          role="menu"
          onClick={(event) => {
            event.stopPropagation();
          }}
          onContextMenu={(event) => event.preventDefault()}
        >
          <button
            className="markdown-contextMenu__item"
            type="button"
            role="menuitem"
            onClick={() => runMarkdownContextAction(handleShowInfo)}
            disabled={!selectedAssetName}
          >
            show info
          </button>
          <button
            className="markdown-contextMenu__item"
            type="button"
            role="menuitem"
            onClick={() => runMarkdownContextAction(handleShowInitial)}
            disabled={!selectedAssetName}
          >
            show initial
          </button>
          <button
            className="markdown-contextMenu__item"
            type="button"
            role="menuitem"
            onClick={() => runMarkdownContextAction(handleFixLatex)}
            disabled={
              !selectedAssetName ||
              !currentMarkdownPath ||
              isTaskRunning("fix_latex", selectedAssetName)
            }
          >
            fix latex
          </button>
          <button
            className="markdown-contextMenu__item"
            type="button"
            role="menuitem"
            onClick={() => runMarkdownContextAction(handleReveal)}
            disabled={!selectedAssetName || !currentMarkdownPath}
          >
            reveal in explorer
          </button>
          {deleteQuestionEnabled ? (
            <button
              className="markdown-contextMenu__item markdown-contextMenu__item--danger"
              type="button"
              role="menuitem"
              onClick={() => {
                setConfirmation({
                  title: "Delete Question",
                  description: `Delete ${currentMarkdownPath ?? "this question"}?`,
                  confirmLabel: "delete question",
                  tone: "danger",
                  action: handleDeleteQuestion
                });
                setMarkdownContextMenu(null);
              }}
            >
              delete question
            </button>
          ) : null}
        </div>
      ) : null}

      {tutorBody
        ? createPortal(
            tutorAskVisible ? (
              <div className="workflow-taskMount workflow-taskMount--compact">
                <div className="workflow-tutorCompact">
                  <textarea
                    aria-label={`Question for tutor ${effectiveTutorIdx ?? ""}`}
                    className="workflow-bar__question"
                    rows={2}
                    value={questionText}
                    onChange={(event) => setQuestionText(event.currentTarget.value)}
                    placeholder="Ask a follow-up question"
                  />
                  <button
                    aria-label="Ask Tutor"
                    className="primary-button workflow-tutorCompact__submit"
                    title="Ask Tutor"
                    type="button"
                    onClick={handleAskTutor}
                    disabled={
                      !selectedAssetName ||
                      !effectiveGroupIdx ||
                      !questionText.trim() ||
                      isTaskRunning("ask_tutor", selectedAssetName)
                    }
                  >
                    <svg viewBox="0 0 16 16" aria-hidden="true">
                      <path
                        d="M2 3.5 14 8 2 12.5l2.6-4.5L2 3.5Z"
                        fill="currentColor"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            ) : null,
            tutorBody,
          )
        : null}

      {activeTaskPanel ? (
        <div className="modal-scrim" role="presentation">
          <div className="modal-card modal-card--wide workflow-modalCard">
            <TaskCenter
              visible={activeTaskPanel}
              onClose={() => setActiveTaskPanel(false)}
              variant="embedded"
            />
          </div>
        </div>
      ) : null}

      <AssetImportDialog
        open={importDialogOpen}
        submitting={importSubmitting}
        errorMessage={importError}
        onClose={() => {
          if (importSubmitting) {
            return;
          }
          setImportError(null);
          setImportDialogOpen(false);
        }}
        onSubmit={handleImportSubmit}
      />

      <ConfirmationDialog
        open={Boolean(confirmation)}
        title={confirmation?.title ?? ""}
        description={confirmation?.description ?? ""}
        confirmLabel={confirmation?.confirmLabel ?? "confirm"}
        tone={confirmation?.tone}
        busy={confirmationBusy}
        onCancel={() => setConfirmation(null)}
        onConfirm={confirmAction}
      />

      {compressPreview ? (
        <div className="modal-scrim" role="presentation">
          <div className="modal-card modal-card--wide">
            <p className="section-kicker">Compress Preview</p>
            <h2>Current selection preview</h2>
            <p className="modal-copy">
              {compressPreview.width && compressPreview.height
                ? `Rendered preview at ${compressPreview.width} x ${compressPreview.height}.`
                : "Rendered preview for the current compress selection."}
            </p>
            <img
              alt="Compressed preview"
              src={compressPreview.dataUrl}
              style={{ width: "100%", borderRadius: "16px", border: "1px solid rgba(15, 23, 42, 0.12)" }}
            />
            <div className="modal-actions">
              <button className="primary-button" type="button" onClick={() => setCompressPreview(null)}>
                close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );

  async function handleShowInfo() {
    if (!selectedAssetName) {
      return;
    }
    for (const name of ["background", "concept", "formula"]) {
      openMarkdownTab({
        assetName: selectedAssetName,
        path: `references/${name}.md`,
        title: `${name}.md`,
        kind: "reference"
      });
    }
  }

  async function handleShowInitial() {
    if (!selectedAssetName) {
      return;
    }
    const initialDocs = flattenMarkdownTree(markdownTree).filter((node) => node.path?.includes("/initial/"));
    if (!initialDocs.length) {
      pushToast({ title: "No initial markdown", description: "No initial files are available for the current asset.", tone: "warning" });
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
        kind: node.kind
      });
    }
  }

  async function handleImportSubmit(payload: ImportAssetInput) {
    try {
      setImportSubmitting(true);
      setImportError(null);
      const task = await api.assets.importAsset(payload);
      setPendingImportIntent(
        payload.compressEnabled
          ? {
              taskId: task.id,
              enterCompressMode: true
            }
          : null
      );
      setImportDialogOpen(false);
      setActiveTaskPanel(true);
      if (payload.compressEnabled) {
        pushToast({
          title: "Import started",
          description: "The UI will switch into compress mode as soon as this asset is ready.",
          tone: "success"
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to start asset import.";
      setImportError(message);
      pushToast({
        title: "Import failed",
        description: message,
        tone: "danger"
      });
    } finally {
      setImportSubmitting(false);
    }
  }

  async function handleFixLatex() {
    if (!selectedAssetName || !currentMarkdownPath) {
      return;
    }
    await api.workflows.submitFixLatex({ assetName: selectedAssetName, markdownPath: currentMarkdownPath });
    setActiveTaskPanel(true);
  }

  async function handleReveal() {
    if (!selectedAssetName || !currentMarkdownPath) {
      return;
    }
    await api.assets.revealAsset(selectedAssetName, currentMarkdownPath);
  }

  async function handleDeleteQuestion() {
    if (!selectedAssetName || !currentMarkdownPath || !effectiveGroupIdx || !effectiveTutorIdx || !api.capabilities.deleteQuestion) {
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

    await api.workflows.submitAskTutor({
      assetName: selectedAssetName,
      groupIdx: effectiveGroupIdx,
      tutorIdx,
      question: questionText.trim()
    });
    setQuestionText("");
    setActiveTaskPanel(true);
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
        tone: "danger"
      });
    } finally {
      setConfirmationBusy(false);
    }
  }

  function runMarkdownContextAction(action: () => Promise<void>) {
    setMarkdownContextMenu(null);
    void action().catch((error) => {
      pushToast({
        title: "Action failed",
        description: error instanceof Error ? error.message : "Unable to complete the action.",
        tone: "danger"
      });
    });
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
      tone: "warning"
    });
    return null;
  }
}

function useSlotElement(id: string) {
  const [element, setElement] = useState<HTMLElement | null>(null);
  useEffect(() => {
    function resolve() {
      setElement(document.getElementById(id));
    }
    resolve();
    const observer = new MutationObserver(resolve);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [id]);
  return element;
}

function latestArtifactPath(events: Array<{ artifactPath: string | null }>): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index]?.artifactPath) {
      return events[index].artifactPath;
    }
  }
  return null;
}

function latestPayload(events: Array<{ payload: Record<string, unknown> | null }>): Record<string, unknown> | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index]?.payload) {
      return events[index].payload;
    }
  }
  return null;
}
