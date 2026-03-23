import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { AssetSummary, ApiSource, MarkdownTreeNode } from "../types";
import { useAppStore } from "../store/appStore";
import { AssetPickerOverlay } from "../../features/sidebar/AssetPickerOverlay";
import { SidebarPane } from "../../features/sidebar/SidebarPane";
import { MarkdownWorkspace } from "../../features/markdown/MarkdownWorkspace";
import { PdfPaneContainer } from "../../features/pdf";
import { useTaskCenter } from "../../features/tasks/TaskCenterContext";
import { WorkflowMarkdownContextMenu } from "../../features/workflows/components/WorkflowMarkdownContextMenu";
import { WorkflowModalHost } from "../../features/workflows/components/WorkflowModalHost";
import { WorkflowTutorDock } from "../../features/workflows/components/WorkflowTutorDock";
import { useWorkflowCommandController } from "../../features/workflows/controllers/useWorkflowCommandController";
import { useWorkflowTaskEffectsBridge } from "../../features/workflows/controllers/useWorkflowTaskEffectsBridge";
import { findGroupEnhancedMarkdownNode } from "../../features/workflows/api/helpers";
import { DesktopTitlebar } from "./DesktopTitlebar";
import { ThemeToggleIcon } from "./ThemeToggleIcon";
import {
  DESKTOP_WORKSPACE_BREAKPOINT_PX,
  SHELL_SPLITTER_WIDTH_PX,
  clampRightRailWidthPx,
  clampSidebarWidthPx,
  resolveDesktopPaneLayout,
  widthToRatio,
} from "./paneLayout";
import { useDesktopShell } from "./desktopShell";

interface WorkbenchShellProps {
  assets: AssetSummary[];
  markdownTree: MarkdownTreeNode[];
  dataSource: ApiSource;
  assetsLoading: boolean;
  assetsError: string | null;
  treeLoading: boolean;
  treeError: string | null;
}

interface PaneDragSession {
  kind: "sidebar" | "rightRail";
  sidebarCollapsed: boolean;
  panelWidthPx: number;
  sidebarWidthPx: number;
  rightRailWidthPx: number;
}

interface AppliedPaneLayout {
  sidebarCollapsed: boolean;
  sidebarWidthPx: number;
  rightRailWidthPx: number;
}

function buildDesktopGridTemplate({
  sidebarCollapsed,
  sidebarWidthPx,
  rightRailWidthPx,
}: AppliedPaneLayout): string {
  return `${sidebarWidthPx}px ${sidebarCollapsed ? 0 : SHELL_SPLITTER_WIDTH_PX}px minmax(0, 1fr) ${SHELL_SPLITTER_WIDTH_PX}px ${rightRailWidthPx}px`;
}

function applyDesktopGridTemplate(
  element: HTMLElement,
  layout: AppliedPaneLayout,
): void {
  element.style.gridTemplateColumns = buildDesktopGridTemplate(layout);
}

export function WorkbenchShell({
  assets,
  markdownTree,
  dataSource,
  assetsLoading,
  assetsError,
  treeLoading,
  treeError,
}: WorkbenchShellProps) {
  const workflow = useWorkflowCommandController();
  const desktopShell = useDesktopShell();
  const { isTaskRunning } = useTaskCenter();
  const theme = useAppStore((state) => state.theme);
  const selectedAssetName = useAppStore((state) => state.selectedAssetName);
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed);
  const sidebarWidthRatio = useAppStore((state) => state.sidebarWidthRatio);
  const rightRailWidthRatio = useAppStore((state) => state.rightRailWidthRatio);
  const appMode = useAppStore((state) => state.appMode);
  const compressSelection = useAppStore((state) => state.compressSelection);
  const setSelectedAssetName = useAppStore((state) => state.setSelectedAssetName);
  const setCurrentPage = useAppStore((state) => state.setCurrentPage);
  const setZoom = useAppStore((state) => state.setZoom);
  const setCompressSelection = useAppStore((state) => state.setCompressSelection);
  const setSidebarWidthRatio = useAppStore((state) => state.setSidebarWidthRatio);
  const setRightRailWidthRatio = useAppStore((state) => state.setRightRailWidthRatio);
  const toggleTheme = useAppStore((state) => state.toggleTheme);
  const openMarkdownTab = useAppStore((state) => state.openMarkdownTab);
  const requestGroupDive = useAppStore((state) => state.requestGroupDive);
  const requestAssetDelete = useAppStore((state) => state.requestAssetDelete);
  const workspaceRef = useRef<HTMLElement | null>(null);
  const dragSessionRef = useRef<PaneDragSession | null>(null);
  const dragPointerIdRef = useRef<number | null>(null);
  const dragSplitterRef = useRef<HTMLElement | null>(null);
  const [isDesktopLayout, setIsDesktopLayout] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }

    return window.innerWidth > DESKTOP_WORKSPACE_BREAKPOINT_PX;
  });
  const [workspaceWidthPx, setWorkspaceWidthPx] = useState(0);
  const showTutorPanel = workflow.tutorAskVisible;
  const canSubmitTutorQuestion =
    Boolean(workflow.selectedAssetName) &&
    Boolean(workflow.effectiveGroupIdx) &&
    Boolean(workflow.questionText.trim()) &&
    !isTaskRunning("ask_tutor", workflow.selectedAssetName);
  const desktopPaneLayout = resolveDesktopPaneLayout({
    containerWidthPx: workspaceWidthPx || 980,
    sidebarCollapsed,
    sidebarWidthRatio,
    rightRailWidthRatio,
  });
  const showDesktopSplitters = isDesktopLayout && desktopPaneLayout.panelWidthPx > 0;
  const committedLayoutRef = useRef<AppliedPaneLayout>({
    sidebarCollapsed,
    sidebarWidthPx: desktopPaneLayout.sidebarWidthPx,
    rightRailWidthPx: desktopPaneLayout.rightRailWidthPx,
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const mediaQuery = window.matchMedia(`(max-width: ${DESKTOP_WORKSPACE_BREAKPOINT_PX}px)`);
    const updateLayoutMode = () => {
      setIsDesktopLayout(!mediaQuery.matches);
    };

    updateLayoutMode();
    mediaQuery.addEventListener("change", updateLayoutMode);
    return () => {
      mediaQuery.removeEventListener("change", updateLayoutMode);
    };
  }, []);

  useEffect(() => {
    if (!showDesktopSplitters || !workspaceRef.current) {
      return undefined;
    }

    const observer = new ResizeObserver((entries) => {
      const [entry] = entries;
      if (!entry) {
        return;
      }

      setWorkspaceWidthPx(entry.contentRect.width);
    });

    observer.observe(workspaceRef.current);
    return () => {
      observer.disconnect();
    };
  }, [showDesktopSplitters]);

  useEffect(() => {
    committedLayoutRef.current = {
      sidebarCollapsed,
      sidebarWidthPx: desktopPaneLayout.sidebarWidthPx,
      rightRailWidthPx: desktopPaneLayout.rightRailWidthPx,
    };

    const workspace = workspaceRef.current;
    if (!workspace) {
      return;
    }

    if (!showDesktopSplitters) {
      workspace.style.removeProperty("grid-template-columns");
      return;
    }

    if (dragSessionRef.current) {
      return;
    }

    applyDesktopGridTemplate(workspace, committedLayoutRef.current);
  }, [
    desktopPaneLayout.rightRailWidthPx,
    desktopPaneLayout.sidebarWidthPx,
    showDesktopSplitters,
    sidebarCollapsed,
  ]);

  useEffect(() => {
    const releaseDragPointerCapture = () => {
      const splitter = dragSplitterRef.current;
      const pointerId = dragPointerIdRef.current;
      if (!splitter || pointerId === null || !splitter.hasPointerCapture(pointerId)) {
        dragPointerIdRef.current = null;
        dragSplitterRef.current = null;
        return;
      }

      splitter.releasePointerCapture(pointerId);
      dragPointerIdRef.current = null;
      dragSplitterRef.current = null;
    };

    const handlePointerMove = (event: PointerEvent) => {
      const session = dragSessionRef.current;
      const workspace = workspaceRef.current;
      if (!session || !workspace) {
        return;
      }

      const bounds = workspace.getBoundingClientRect();
      const visibleSplitterCount = session.sidebarCollapsed ? 1 : 2;
      const panelWidthPx = Math.max(0, bounds.width - visibleSplitterCount * SHELL_SPLITTER_WIDTH_PX);
      session.panelWidthPx = panelWidthPx;

      if (session.kind === "sidebar" && !session.sidebarCollapsed) {
        session.sidebarWidthPx = clampSidebarWidthPx(
          event.clientX - bounds.left - SHELL_SPLITTER_WIDTH_PX / 2,
          panelWidthPx,
          session.rightRailWidthPx,
        );
      } else {
        session.rightRailWidthPx = clampRightRailWidthPx(
          bounds.right - event.clientX - SHELL_SPLITTER_WIDTH_PX / 2,
          panelWidthPx,
          session.sidebarWidthPx,
        );
      }

      applyDesktopGridTemplate(workspace, {
        sidebarCollapsed: session.sidebarCollapsed,
        sidebarWidthPx: session.sidebarWidthPx,
        rightRailWidthPx: session.rightRailWidthPx,
      });
    };

    const stopDragging = (commit: boolean) => {
      const session = dragSessionRef.current;
      dragSessionRef.current = null;
      document.body.classList.remove("is-resizing-panes");
      releaseDragPointerCapture();

      if (!session) {
        return;
      }

      if (!commit) {
        if (workspaceRef.current && showDesktopSplitters) {
          applyDesktopGridTemplate(workspaceRef.current, committedLayoutRef.current);
        }
        return;
      }

      if (session.panelWidthPx <= 0) {
        return;
      }

      if (session.kind === "sidebar" && !session.sidebarCollapsed) {
        setSidebarWidthRatio(widthToRatio(session.sidebarWidthPx, session.panelWidthPx));
        return;
      }

      setRightRailWidthRatio(widthToRatio(session.rightRailWidthPx, session.panelWidthPx));
    };
    const handlePointerUp = () => {
      stopDragging(true);
    };
    const handlePointerCancel = () => {
      stopDragging(false);
    };
    const handleWindowBlur = () => {
      stopDragging(false);
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        stopDragging(false);
      }
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerCancel);
    window.addEventListener("blur", handleWindowBlur);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerCancel);
      window.removeEventListener("blur", handleWindowBlur);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      document.body.classList.remove("is-resizing-panes");
      releaseDragPointerCapture();
    };
  }, [setRightRailWidthRatio, setSidebarWidthRatio, showDesktopSplitters]);

  useWorkflowTaskEffectsBridge({
    pendingImportIntent: workflow.pendingImportIntent,
    setPendingImportIntent: workflow.setPendingImportIntent,
    setCompressPreview: workflow.setCompressPreview,
    feynman: workflow.feynman,
    setFeynman: workflow.setFeynman,
  });

  const sidebarPanel = (
    <aside className="shell__panel shell__panel--sidebar">
      <SidebarPane
        markdownTree={markdownTree}
        treeLoading={treeLoading}
        treeError={treeError}
      />
    </aside>
  );

  const markdownPanel = (
    <section className="shell__panel shell__panel--markdown">
      <MarkdownWorkspace selectedAssetName={selectedAssetName} />
    </section>
  );

  const rightRailPanel = (
    <aside className="shell__panel shell__panel--rightRail">
      <section className="shell__rightSlot shell__rightSlot--pdf">
        <div className="shell__rightSlotBody">
          <PdfPaneContainer
            assetName={selectedAssetName}
            appMode={appMode}
            toolbarSlot={
              <button
                className="pdf-pane__button pdf-pane__button--secondary"
                type="button"
                onClick={() => workflow.setActiveTaskPanel(true)}
                disabled={!selectedAssetName}
              >
                workflow
              </button>
            }
            initialCompressSelection={compressSelection}
            onAssetStateChange={(nextAssetState) => {
              if (!nextAssetState) {
                return;
              }

              setCurrentPage(nextAssetState.uiState.currentPage);
              setZoom(nextAssetState.uiState.zoom);
            }}
            onGroupedBlockActivate={(groupIdx) => {
              if (!selectedAssetName) {
                return;
              }

              const enhancedNode = findGroupEnhancedMarkdownNode(markdownTree, groupIdx);
              if (enhancedNode?.path) {
                openMarkdownTab({
                  assetName: selectedAssetName,
                  path: enhancedNode.path,
                  title: enhancedNode.title,
                  kind: enhancedNode.kind,
                });
                return;
              }

              requestGroupDive(selectedAssetName, groupIdx);
            }}
            onCompressSelectionChange={(selection) => {
              setCompressSelection(selection);
            }}
          />
        </div>
      </section>
      {showTutorPanel ? (
        <section className="shell__rightSlot shell__rightSlot--tasks">
          <div className="shell__rightSlotBody">
            <WorkflowTutorDock
              visible={workflow.tutorAskVisible}
              questionText={workflow.questionText}
              effectiveTutorIdx={workflow.effectiveTutorIdx}
              canSubmit={canSubmitTutorQuestion}
              onQuestionChange={workflow.setQuestionText}
              onSubmit={() => {
                void workflow.handleAskTutor();
              }}
            />
          </div>
        </section>
      ) : null}
    </aside>
  );

  function startPaneDrag(kind: "sidebar" | "rightRail") {
    return (event: ReactPointerEvent<HTMLDivElement>) => {
      const workspace = workspaceRef.current;
      if (!workspace || !showDesktopSplitters || (kind === "sidebar" && sidebarCollapsed)) {
        return;
      }

      const bounds = workspace.getBoundingClientRect();
      const liveLayout = resolveDesktopPaneLayout({
        containerWidthPx: bounds.width,
        sidebarCollapsed,
        sidebarWidthRatio,
        rightRailWidthRatio,
      });

      event.preventDefault();
      dragSessionRef.current = {
        kind,
        sidebarCollapsed,
        panelWidthPx: liveLayout.panelWidthPx,
        sidebarWidthPx: liveLayout.sidebarWidthPx,
        rightRailWidthPx: liveLayout.rightRailWidthPx,
      };
      applyDesktopGridTemplate(workspace, {
        sidebarCollapsed,
        sidebarWidthPx: liveLayout.sidebarWidthPx,
        rightRailWidthPx: liveLayout.rightRailWidthPx,
      });
      event.currentTarget.setPointerCapture(event.pointerId);
      dragPointerIdRef.current = event.pointerId;
      dragSplitterRef.current = event.currentTarget;
      document.body.classList.add("is-resizing-panes");
    };
  }

  return (
    <div className={`shell${desktopShell.isDesktopShell ? " shell--desktop" : ""}`}>
      {desktopShell.isDesktopShell ? (
        <DesktopTitlebar
          theme={theme}
          selectedAssetName={selectedAssetName}
          isMaximized={desktopShell.isMaximized}
          onToggleTheme={toggleTheme}
          onMinimize={() => {
            void desktopShell.minimize();
          }}
          onToggleMaximize={() => {
            void desktopShell.toggleMaximize();
          }}
          onClose={() => {
            void desktopShell.close();
          }}
        />
      ) : (
        <div className="shell__themeToggleWrap">
          <button
            className="shell__themeToggle"
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            <ThemeToggleIcon theme={theme} />
          </button>
        </div>
      )}

      {showDesktopSplitters ? (
        <main
          className={`shell__workspace shell__workspace--desktop${sidebarCollapsed ? " is-sidebar-collapsed" : ""}`}
          ref={workspaceRef}
        >
          {sidebarPanel}
          <div
            className={`shell__splitter shell__splitter--left${sidebarCollapsed ? " is-hidden" : ""}`}
            role="separator"
            aria-hidden={sidebarCollapsed}
            onPointerDown={startPaneDrag("sidebar")}
          />
          {markdownPanel}
          <div
            className="shell__splitter shell__splitter--right"
            role="separator"
            aria-label="Resize markdown and PDF panes"
            onPointerDown={startPaneDrag("rightRail")}
          />
          {rightRailPanel}
        </main>
      ) : (
        <main
          className={`shell__workspace${sidebarCollapsed ? " is-sidebar-collapsed" : ""}`}
          ref={workspaceRef}
        >
          {sidebarPanel}
          {markdownPanel}
          {rightRailPanel}
        </main>
      )}

      {!selectedAssetName ? (
        <AssetPickerOverlay
          assets={assets}
          dataSource={dataSource}
          loading={assetsLoading}
          error={assetsError}
          reserveDesktopTitlebarSpace={desktopShell.isDesktopShell}
          onCreateAsset={() => workflow.setImportDialogOpen(true)}
          onSelect={(assetName) => setSelectedAssetName(assetName)}
          onDeleteAsset={(assetName) => {
            requestAssetDelete(assetName);
          }}
        />
      ) : null}

      <WorkflowMarkdownContextMenu
        menu={workflow.markdownContextMenu}
        selectedAssetName={workflow.selectedAssetName}
        currentMarkdownPath={workflow.currentMarkdownPath}
        deleteQuestionEnabled={workflow.deleteQuestionEnabled}
        fixLatexRunning={isTaskRunning("fix_latex", workflow.selectedAssetName)}
        onClose={workflow.closeMarkdownContextMenu}
        runAction={workflow.runMarkdownContextAction}
        onShowInfo={workflow.handleShowInfo}
        onShowInitial={workflow.handleShowInitial}
        onFixLatex={workflow.handleFixLatex}
        onReveal={workflow.handleReveal}
        onDeleteQuestion={workflow.openDeleteQuestionConfirmation}
      />

      <WorkflowModalHost
        activeTaskPanel={workflow.activeTaskPanel}
        importDialogOpen={workflow.importDialogOpen}
        importSubmitting={workflow.importSubmitting}
        importError={workflow.importError}
        confirmation={workflow.confirmation}
        confirmationBusy={workflow.confirmationBusy}
        compressPreview={workflow.compressPreview}
        onCloseTaskPanel={() => workflow.setActiveTaskPanel(false)}
        onCloseImportDialog={workflow.closeImportDialog}
        onImportSubmit={workflow.handleImportSubmit}
        onCancelConfirmation={workflow.closeConfirmation}
        onConfirmAction={workflow.confirmAction}
        onCloseCompressPreview={() => workflow.setCompressPreview(null)}
      />
    </div>
  );
}
