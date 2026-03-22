import { AssetSummary, ApiSource, MarkdownTreeNode } from "../types";
import { SHELL_SLOT_IDS } from "../shellSlots";
import { useAppStore } from "../store/appStore";
import { AssetPickerOverlay } from "../../features/sidebar/AssetPickerOverlay";
import { SidebarPane } from "../../features/sidebar/SidebarPane";
import { MarkdownWorkspace } from "../../features/markdown/MarkdownWorkspace";
import { PdfPaneContainer } from "../../features/pdf";
import {
  deriveTutorContext,
  findGroupEnhancedMarkdownNode,
} from "../../features/workflows/api/helpers";

interface WorkbenchShellProps {
  assets: AssetSummary[];
  markdownTree: MarkdownTreeNode[];
  dataSource: ApiSource;
  assetsLoading: boolean;
  assetsError: string | null;
  treeLoading: boolean;
  treeError: string | null;
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
  const theme = useAppStore((state) => state.theme);
  const selectedAssetName = useAppStore((state) => state.selectedAssetName);
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed);
  const appMode = useAppStore((state) => state.appMode);
  const compressSelection = useAppStore((state) => state.compressSelection);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const setActiveTaskPanel = useAppStore((state) => state.setActiveTaskPanel);
  const setSelectedAssetName = useAppStore((state) => state.setSelectedAssetName);
  const setImportDialogOpen = useAppStore((state) => state.setImportDialogOpen);
  const setCurrentPage = useAppStore((state) => state.setCurrentPage);
  const setZoom = useAppStore((state) => state.setZoom);
  const setCompressSelection = useAppStore((state) => state.setCompressSelection);
  const toggleTheme = useAppStore((state) => state.toggleTheme);
  const openMarkdownTab = useAppStore((state) => state.openMarkdownTab);
  const requestGroupDive = useAppStore((state) => state.requestGroupDive);
  const requestAssetDelete = useAppStore((state) => state.requestAssetDelete);
  const tutorContext = deriveTutorContext(currentMarkdownPath);
  const showTutorPanel = tutorContext !== null;

  return (
    <div className="shell">
      <div className="shell__themeToggleWrap">
        <button
          className="shell__themeToggle"
          type="button"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? "light" : "dark"}
        </button>
      </div>
      <main className={`shell__workspace${sidebarCollapsed ? " is-sidebar-collapsed" : ""}`}>
        <aside className="shell__panel shell__panel--sidebar">
          <SidebarPane
            markdownTree={markdownTree}
            treeLoading={treeLoading}
            treeError={treeError}
          />
        </aside>

        <section className="shell__panel shell__panel--markdown">
          <MarkdownWorkspace selectedAssetName={selectedAssetName} markdownTree={markdownTree} />
        </section>

        <aside className="shell__panel shell__panel--rightRail">
          <section className="shell__rightSlot shell__rightSlot--pdf" id={SHELL_SLOT_IDS.pdfPane}>
            <div className="shell__rightSlotBody">
              <PdfPaneContainer
                assetName={selectedAssetName}
                appMode={appMode}
                toolbarSlot={
                  <button
                    className="pdf-pane__button pdf-pane__button--secondary"
                    type="button"
                    onClick={() => setActiveTaskPanel(true)}
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
              <div className="shell__rightSlotBody" id={SHELL_SLOT_IDS.tutorPanel} />
            </section>
          ) : null}
        </aside>
      </main>

      {!selectedAssetName ? (
        <AssetPickerOverlay
          assets={assets}
          dataSource={dataSource}
          loading={assetsLoading}
          error={assetsError}
          onCreateAsset={() => setImportDialogOpen(true)}
          onSelect={(assetName) => setSelectedAssetName(assetName)}
          onDeleteAsset={(assetName) => {
            requestAssetDelete(assetName);
          }}
        />
      ) : null}
    </div>
  );
}
