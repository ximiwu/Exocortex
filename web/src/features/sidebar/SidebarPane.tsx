import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import { AssetState, MarkdownTreeNode } from "../../app/types";
import { useAppStore } from "../../app/store/appStore";
import { useToasts } from "../tasks/ToastProvider";
import { useTaskCenter } from "../tasks/TaskCenterContext";
import { Modal } from "../shared/Modal";
import { MarkdownTree } from "./MarkdownTree";
import {
  collectLeafPaths,
  filterTreeByPaths,
  resolveLocatePageIndex,
} from "./treeUtils";

interface SidebarPaneProps {
  markdownTree: MarkdownTreeNode[];
  treeLoading: boolean;
  treeError: string | null;
}

const EMPTY_NODE_IDS: string[] = [];
const DEFAULT_LINE_CLAMP = 1;
const DEFAULT_FONT_SIZE = 14;

function clampLineClamp(value: number): number {
  return Math.max(1, Math.min(6, Math.floor(value)));
}

function clampFontSize(value: number): number {
  return Math.max(10, Math.min(24, Math.floor(value)));
}

export function SidebarPane({ markdownTree, treeLoading, treeError }: SidebarPaneProps) {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
  const { pushToast } = useToasts();
  const { isGroupTaskRunning, trackSubmittedTask } = useTaskCenter();
  const selectedAssetName = useAppStore((state) => state.selectedAssetName);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed);
  const sidebarCollapsedNodeIdsByAsset = useAppStore((state) => state.sidebarCollapsedNodeIdsByAsset);
  const sidebarRevealTarget = useAppStore((state) => state.sidebarRevealTarget);
  const openTabs = useAppStore((state) => state.openTabs);
  const setSidebarCollapsed = useAppStore((state) => state.setSidebarCollapsed);
  const toggleSidebarNode = useAppStore((state) => state.toggleSidebarNode);
  const openMarkdownTab = useAppStore((state) => state.openMarkdownTab);
  const openMarkdownTabs = useAppStore((state) => state.openMarkdownTabs);
  const closeMarkdownTabs = useAppStore((state) => state.closeMarkdownTabs);
  const clearSidebarRevealTarget = useAppStore((state) => state.clearSidebarRevealTarget);
  const requestPdfNavigation = useAppStore((state) => state.requestPdfNavigation);
  const treeScrollRef = useRef<HTMLDivElement | null>(null);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [sidebarTextLineClamp, setSidebarTextLineClamp] = useState(DEFAULT_LINE_CLAMP);
  const [sidebarFontSizePx, setSidebarFontSizePx] = useState(DEFAULT_FONT_SIZE);
  const [lineClampDraft, setLineClampDraft] = useState(String(DEFAULT_LINE_CLAMP));
  const [fontSizeDraft, setFontSizeDraft] = useState(String(DEFAULT_FONT_SIZE));
  const collapsedNodeIds = selectedAssetName
    ? sidebarCollapsedNodeIdsByAsset[selectedAssetName] ?? EMPTY_NODE_IDS
    : EMPTY_NODE_IDS;
  const openPaths = selectedAssetName
    ? openTabs.filter((tab) => tab.assetName === selectedAssetName).map((tab) => tab.path)
    : [];

  const visibleTree = filterTreeByPaths(markdownTree, new Set(openPaths));
  const activeScrollKey =
    selectedAssetName && currentMarkdownPath ? `${selectedAssetName}:${currentMarkdownPath}` : null;
  const revealKey =
    sidebarRevealTarget ? `${sidebarRevealTarget.assetName}:${sidebarRevealTarget.path}:${sidebarRevealTarget.nonce}` : null;

  useLayoutEffect(() => {
    if (!revealKey || !sidebarRevealTarget || !activeScrollKey || treeLoading || sidebarCollapsed) {
      return;
    }

    if (
      sidebarRevealTarget.assetName !== selectedAssetName ||
      sidebarRevealTarget.path !== currentMarkdownPath
    ) {
      return;
    }

    const container = treeScrollRef.current;
    if (!container) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      const activeElement = container.querySelector<HTMLElement>('[data-sidebar-active="true"]');
      if (!activeElement) {
        return;
      }

      activeElement.scrollIntoView({
        block: "center",
        inline: "nearest",
        behavior: "smooth",
      });
      clearSidebarRevealTarget();
    });

    return () => cancelAnimationFrame(frame);
  }, [
    activeScrollKey,
    clearSidebarRevealTarget,
    currentMarkdownPath,
    revealKey,
    selectedAssetName,
    sidebarCollapsed,
    sidebarRevealTarget,
    treeLoading,
    visibleTree,
  ]);

  useEffect(() => {
    let cancelled = false;

    void api.system
      .getConfig()
      .then((config) => {
        if (cancelled) {
          return;
        }

        const nextLineClamp = clampLineClamp(config.sidebarTextLineClamp ?? DEFAULT_LINE_CLAMP);
        const nextFontSize = clampFontSize(config.sidebarFontSizePx ?? DEFAULT_FONT_SIZE);
        setSidebarTextLineClamp(nextLineClamp);
        setSidebarFontSizePx(nextFontSize);
        setLineClampDraft(String(nextLineClamp));
        setFontSizeDraft(String(nextFontSize));
      })
      .catch((error) => {
        console.warn("Failed to load sidebar display settings", error);
      });

    return () => {
      cancelled = true;
    };
  }, [api.system]);

  async function saveDisplaySettings() {
    const nextLineClamp = clampLineClamp(Number(lineClampDraft) || DEFAULT_LINE_CLAMP);
    const nextFontSize = clampFontSize(Number(fontSizeDraft) || DEFAULT_FONT_SIZE);

    setSettingsSaving(true);
    try {
      const persisted = await api.system.updateConfig({
        sidebarTextLineClamp: nextLineClamp,
        sidebarFontSizePx: nextFontSize,
      });
      const persistedLineClamp = clampLineClamp(persisted.sidebarTextLineClamp ?? nextLineClamp);
      const persistedFontSize = clampFontSize(persisted.sidebarFontSizePx ?? nextFontSize);
      setSidebarTextLineClamp(persistedLineClamp);
      setSidebarFontSizePx(persistedFontSize);
      setLineClampDraft(String(persistedLineClamp));
      setFontSizeDraft(String(persistedFontSize));
      setSettingsModalOpen(false);
    } catch (error) {
      console.warn("Failed to save sidebar display settings", error);
    } finally {
      setSettingsSaving(false);
    }
  }

  return (
    <div className={`sidebar${sidebarCollapsed ? " is-collapsed" : ""}`}>
      <div className="sidebar__toolbar">
        <button
          className="sidebar__toolbarButton"
          type="button"
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path
              d="M2 3.5h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2zm0 4h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2zm0 4h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2z"
              fill="currentColor"
            />
          </svg>
        </button>

        <div className="sidebar__toolbarTitle">Contents</div>
        <div className="sidebar__toolbarSpacer" />
        <div className="sidebar__toolbarActions">
          <button
            className="sidebar__toolbarButton"
            type="button"
            onClick={() => {
              setLineClampDraft(String(sidebarTextLineClamp));
              setFontSizeDraft(String(sidebarFontSizePx));
              setSettingsModalOpen(true);
            }}
            aria-label="Sidebar display settings"
            title="Sidebar display settings"
          >
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path
                d="M9.72 1.7a.75.75 0 0 1 .96.45l.38 1.08a4.88 4.88 0 0 1 .92.53l1.08-.41a.75.75 0 0 1 .98.43l.58 1.39a.75.75 0 0 1-.38.99l-1.03.5c.03.17.04.34.04.52 0 .18-.01.35-.04.52l1.03.5a.75.75 0 0 1 .38.99l-.58 1.39a.75.75 0 0 1-.98.43l-1.08-.41a4.88 4.88 0 0 1-.92.53l-.38 1.08a.75.75 0 0 1-.96.45l-1.45-.46a.75.75 0 0 1-.5-.94l.34-1.08a4.83 4.83 0 0 1-.8-.58l-1.08.4a.75.75 0 0 1-.98-.43l-.58-1.39a.75.75 0 0 1 .38-.99l1.03-.5a4.13 4.13 0 0 1 0-1.04l-1.03-.5a.75.75 0 0 1-.38-.99l.58-1.39a.75.75 0 0 1 .98-.43l1.08.4c.24-.22.5-.41.8-.58l-.34-1.08a.75.75 0 0 1 .5-.94zM8 5.75a2.25 2.25 0 1 0 0 4.5 2.25 2.25 0 0 0 0-4.5z"
                fill="currentColor"
              />
            </svg>
          </button>
        </div>
      </div>

      <div className="sidebar__treePane">
        <div className="sidebar__treeScroll" ref={treeScrollRef}>
          {treeLoading ? <div className="sidebar__empty">Loading groups...</div> : null}
          {treeError ? <div className="sidebar__error">{treeError}</div> : null}
          {!treeLoading && !treeError ? (
            <MarkdownTree
              hasAsset={Boolean(selectedAssetName)}
              nodes={visibleTree}
              fullTree={markdownTree}
              emptyMessage="No markdown tabs are open in this asset."
              currentPath={currentMarkdownPath}
              openPaths={openPaths}
              collapsedNodeIds={collapsedNodeIds}
              sidebarTextLineClamp={sidebarTextLineClamp}
              sidebarFontSizePx={sidebarFontSizePx}
              onToggleNode={(nodeId) => {
                if (!selectedAssetName) {
                  return;
                }
                toggleSidebarNode(selectedAssetName, nodeId);
              }}
              onOpenPath={(path, title, kind) => {
                if (!selectedAssetName) {
                  return;
                }

                openMarkdownTab({
                  assetName: selectedAssetName,
                  path,
                  title,
                  kind,
                }, { source: "sidebar" });
              }}
              onOpenPaths={(nodesToOpen) => {
                if (!selectedAssetName) {
                  return;
                }

                openMarkdownTabs(
                  nodesToOpen.map((node) => ({
                    assetName: selectedAssetName,
                    path: node.path,
                    title: node.title,
                    kind: node.kind,
                  })),
                  currentMarkdownPath,
                );
              }}
              onClosePaths={(paths) => {
                if (!selectedAssetName) {
                  return;
                }
                closeMarkdownTabs(selectedAssetName, paths);
              }}
              onLocateInPdf={async (groupIdx) => {
                if (!selectedAssetName) {
                  return;
                }

                const cachedState = queryClient.getQueryData<AssetState>(
                  queryKeys.assetState(selectedAssetName),
                ) ?? null;
                const state = cachedState ?? (await api.assets.getState(selectedAssetName));
                const pageIndex = resolveLocatePageIndex(state, groupIdx);
                if (pageIndex === null) {
                  console.warn("Unable to locate group in PDF.", {
                    assetName: selectedAssetName,
                    groupIdx,
                  });
                  return;
                }

                requestPdfNavigation(selectedAssetName, pageIndex + 1);
              }}
              onGenerateFlashcard={async (groupIdx) => {
                if (!selectedAssetName) {
                  return;
                }
                if (isGroupTaskRunning("flashcard", selectedAssetName, groupIdx)) {
                  pushToast({
                    title: "Flashcard already running",
                    description: `Group ${groupIdx} is already in progress.`,
                    tone: "warning",
                  });
                  return;
                }

                try {
                  const task = await api.workflows.submitFlashcard({
                    assetName: selectedAssetName,
                    groupIdx,
                  });
                  trackSubmittedTask(task);
                } catch (error) {
                  if (error instanceof Error && error.message === "An equivalent task is already in progress.") {
                    pushToast({
                      title: "Flashcard already running",
                      description: `Group ${groupIdx} is already in progress.`,
                      tone: "warning",
                    });
                    return;
                  }
                  pushToast({
                    title: "Flashcard failed",
                    description: error instanceof Error ? error.message : "Unable to start flashcard generation.",
                    tone: "danger",
                  });
                }
              }}
              onRevealFlashcard={async (groupIdx) => {
                if (!selectedAssetName) {
                  return;
                }

                await api.assets.revealAsset(selectedAssetName, `group_data/${groupIdx}/flashcard/apkg`);
              }}
              onDeleteGroup={async (groupIdx, node) => {
                if (!selectedAssetName) {
                  return;
                }

                closeMarkdownTabs(selectedAssetName, collectLeafPaths(node));
                const nextState = await api.pdf.deleteGroup(selectedAssetName, groupIdx);
                queryClient.setQueryData(queryKeys.assetState(selectedAssetName), nextState);
                await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(selectedAssetName) });
              }}
              onDeleteTutor={async (groupIdx, tutorIdx, node) => {
                if (!selectedAssetName) {
                  return;
                }

                closeMarkdownTabs(selectedAssetName, collectLeafPaths(node));
                await api.workflows.deleteTutorSession({
                  assetName: selectedAssetName,
                  groupIdx,
                  tutorIdx,
                });
                await queryClient.invalidateQueries({ queryKey: queryKeys.assetState(selectedAssetName) });
                await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(selectedAssetName) });
              }}
              onDeleteAsk={async (groupIdx, tutorIdx, path) => {
                if (!selectedAssetName) {
                  return;
                }

                closeMarkdownTabs(selectedAssetName, [path]);
                await api.workflows.deleteQuestion({
                  assetName: selectedAssetName,
                  groupIdx,
                  tutorIdx,
                  markdownPath: path,
                });
                await queryClient.invalidateQueries({ queryKey: queryKeys.assetState(selectedAssetName) });
                await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(selectedAssetName) });
              }}
              onRenameAlias={async (node, alias) => {
                if (!selectedAssetName) {
                  return;
                }
                await api.markdown.renameNodeAlias({
                  nodeId: node.id,
                  assetName: selectedAssetName,
                  path: node.path,
                  alias,
                });
                await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(selectedAssetName) });
              }}
              onReorderSiblings={async (parentId, orderedNodeIds) => {
                if (!selectedAssetName) {
                  return;
                }
                await api.markdown.reorderSiblings({
                  assetName: selectedAssetName,
                  parentId,
                  orderedNodeIds,
                });
                await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(selectedAssetName) });
              }}
            />
          ) : null}
        </div>
      </div>
      <Modal
        open={settingsModalOpen}
        onClose={() => {
          if (settingsSaving) {
            return;
          }
          setSettingsModalOpen(false);
        }}
        labelledBy="sidebar-display-settings-title"
      >
        <div className="sidebarSettingsModal">
          <h2 id="sidebar-display-settings-title">sidebar display settings</h2>
          <div className="form-grid">
            <label className="form-field">
              <span>line clamp (1-6)</span>
              <input
                type="number"
                min={1}
                max={6}
                value={lineClampDraft}
                onChange={(event) => setLineClampDraft(event.currentTarget.value)}
              />
            </label>
            <label className="form-field">
              <span>font size px (10-24)</span>
              <input
                type="number"
                min={10}
                max={24}
                value={fontSizeDraft}
                onChange={(event) => setFontSizeDraft(event.currentTarget.value)}
              />
            </label>
          </div>
          <div className="modal-actions">
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                if (settingsSaving) {
                  return;
                }
                setSettingsModalOpen(false);
              }}
            >
              cancel
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                void saveDisplaySettings();
              }}
              disabled={settingsSaving}
            >
              save
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
