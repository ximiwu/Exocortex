import { useLayoutEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import { MarkdownTreeNode } from "../../app/types";
import { useAppStore } from "../../app/store/appStore";
import { MarkdownTree } from "./MarkdownTree";

interface SidebarPaneProps {
  markdownTree: MarkdownTreeNode[];
  treeLoading: boolean;
  treeError: string | null;
}

const EMPTY_NODE_IDS: string[] = [];

export function SidebarPane({ markdownTree, treeLoading, treeError }: SidebarPaneProps) {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
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
  const closeMarkdownTab = useAppStore((state) => state.closeMarkdownTab);
  const closeMarkdownTabs = useAppStore((state) => state.closeMarkdownTabs);
  const clearSidebarRevealTarget = useAppStore((state) => state.clearSidebarRevealTarget);
  const treeScrollRef = useRef<HTMLDivElement | null>(null);
  const collapsedNodeIds = selectedAssetName
    ? sidebarCollapsedNodeIdsByAsset[selectedAssetName] ?? EMPTY_NODE_IDS
    : EMPTY_NODE_IDS;
  const openPaths = selectedAssetName
    ? openTabs.filter((tab) => tab.assetName === selectedAssetName).map((tab) => tab.path)
    : [];

  const openableNodes = flattenOpenableNodes(markdownTree);
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

        <div className="sidebar__toolbarTitle">Exocortex</div>
        <div className="sidebar__toolbarSpacer" />
        <div className="sidebar__toolbarActions">
          <button
            className="sidebar__toolbarButton"
            type="button"
            onClick={() => {
              if (!selectedAssetName || !openableNodes.length) {
                return;
              }

              openMarkdownTabs(
                openableNodes.map((node) => ({
                  assetName: selectedAssetName,
                  path: node.path,
                  title: node.title,
                  kind: node.kind,
                })),
                currentMarkdownPath,
              );
            }}
            aria-label="Open all markdown under asset"
            title="Open all markdown under asset"
            disabled={!selectedAssetName || !openableNodes.length}
          >
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path
                d="M8 1.5a.75.75 0 0 1 .75.75v5.19l1.72-1.72a.75.75 0 1 1 1.06 1.06L8 10.31 4.47 6.78a.75.75 0 1 1 1.06-1.06l1.72 1.72V2.25A.75.75 0 0 1 8 1.5z"
                fill="currentColor"
              />
              <path
                d="M2.5 10.5a.75.75 0 0 1 .75.75v1.25c0 .55.45 1 1 1h7.5c.55 0 1-.45 1-1v-1.25a.75.75 0 0 1 1.5 0v1.25c0 1.38-1.12 2.5-2.5 2.5h-7.5c-1.38 0-2.5-1.12-2.5-2.5v-1.25a.75.75 0 0 1 .75-.75z"
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
              collapsedNodeIds={collapsedNodeIds}
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
              onClosePath={(path) => {
                if (!selectedAssetName) {
                  return;
                }
                closeMarkdownTab(selectedAssetName, path);
              }}
              onCloseBranch={(paths) => {
                if (!selectedAssetName) {
                  return;
                }
                closeMarkdownTabs(selectedAssetName, paths);
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
    </div>
  );
}

function flattenOpenableNodes(nodes: MarkdownTreeNode[]): Array<{ path: string; title: string; kind: string }> {
  const result: Array<{ path: string; title: string; kind: string }> = [];

  for (const node of nodes) {
    if (node.path) {
      result.push({
        path: node.path,
        title: node.title,
        kind: node.kind,
      });
    }

    if (node.children.length) {
      result.push(...flattenOpenableNodes(node.children));
    }
  }

  return result;
}

function filterTreeByPaths(nodes: MarkdownTreeNode[], openPaths: Set<string>): MarkdownTreeNode[] {
  return nodes.flatMap((node) => {
    const children = filterTreeByPaths(node.children, openPaths);
    const isOpenLeaf = Boolean(node.path && openPaths.has(node.path));

    if (!isOpenLeaf && children.length === 0) {
      return [];
    }

    return [
      {
        ...node,
        children,
      },
    ];
  });
}
