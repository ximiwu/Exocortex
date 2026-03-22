import { useEffect, useMemo, useRef, useState, type DragEvent as ReactDragEvent, type MouseEvent as ReactMouseEvent } from "react";
import { createPortal } from "react-dom";

import { MarkdownTreeNode } from "../../app/types";

type DropPosition = "before" | "after";

interface MarkdownTreeProps {
  hasAsset: boolean;
  nodes: MarkdownTreeNode[];
  fullTree: MarkdownTreeNode[];
  emptyMessage?: string;
  currentPath: string | null;
  collapsedNodeIds: string[];
  onToggleNode: (nodeId: string) => void;
  onOpenPath: (path: string, title: string, kind: string) => void;
  onClosePath: (path: string) => void;
  onCloseBranch: (paths: string[]) => void;
  onRenameAlias: (node: MarkdownTreeNode, alias: string) => Promise<void>;
  onReorderSiblings: (parentId: string | null, orderedNodeIds: string[]) => Promise<void>;
}

interface TreeRenderNode extends MarkdownTreeNode {
  parentId: string | null;
  depth: number;
  children: TreeRenderNode[];
}

interface ContextMenuState {
  nodeId: string;
  x: number;
  y: number;
}

interface DragOverState {
  nodeId: string;
  position: DropPosition;
}

function hasActiveDescendant(node: MarkdownTreeNode, currentPath: string | null): boolean {
  if (!currentPath) {
    return false;
  }
  if (node.path === currentPath) {
    return true;
  }
  return node.children.some((child) => hasActiveDescendant(child, currentPath));
}

function collectLeafPaths(node: MarkdownTreeNode): string[] {
  if (node.path) {
    return [node.path];
  }

  return node.children.flatMap(collectLeafPaths);
}

function buildRenderTree(
  nodes: MarkdownTreeNode[],
  parentId: string | null,
  depth: number,
): TreeRenderNode[] {
  return nodes.map((node) => ({
    ...node,
    parentId,
    depth,
    children: buildRenderTree(node.children, node.id, depth + 1),
  }));
}

function findNode(nodes: MarkdownTreeNode[], nodeId: string): MarkdownTreeNode | null {
  for (const node of nodes) {
    if (node.id === nodeId) {
      return node;
    }
    const child = findNode(node.children, nodeId);
    if (child) {
      return child;
    }
  }
  return null;
}

function findSiblings(nodes: MarkdownTreeNode[], parentId: string | null): MarkdownTreeNode[] | null {
  if (parentId === null) {
    return nodes;
  }
  const parent = findNode(nodes, parentId);
  return parent?.children ?? null;
}

function canRenameNode(node: MarkdownTreeNode): boolean {
  return node.kind === "group" || node.kind === "tutor" || (node.path !== null && node.children.length === 0);
}

export function MarkdownTree({
  hasAsset,
  nodes,
  fullTree,
  emptyMessage,
  currentPath,
  collapsedNodeIds,
  onToggleNode,
  onOpenPath,
  onClosePath,
  onCloseBranch,
  onRenameAlias,
  onReorderSiblings,
}: MarkdownTreeProps) {
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [savingNodeId, setSavingNodeId] = useState<string | null>(null);
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<DragOverState | null>(null);
  const cancelRenameRef = useRef(false);
  const renderNodes = useMemo(() => buildRenderTree(nodes, null, 0), [nodes]);

  useEffect(() => {
    if (!contextMenu) {
      return undefined;
    }

    const closeMenu = () => setContextMenu(null);
    const handleKeyDown = () => setContextMenu(null);

    window.addEventListener("click", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [contextMenu]);

  useEffect(() => {
    setContextMenu(null);
    setEditingNodeId(null);
    setEditingValue("");
    setSavingNodeId(null);
    setDraggingNodeId(null);
    setDragOver(null);
  }, [currentPath, nodes]);

  if (!nodes.length) {
    if (!hasAsset) {
      return <div className="sidebar__empty">Choose an asset to load its groups.</div>;
    }

    return <div className="sidebar__empty">{emptyMessage ?? "No groups are available for this asset yet."}</div>;
  }

  function beginRename(node: MarkdownTreeNode) {
    if (!canRenameNode(node)) {
      return;
    }
    cancelRenameRef.current = false;
    setContextMenu(null);
    setEditingNodeId(node.id);
    setEditingValue(node.title);
  }

  async function submitRename(node: MarkdownTreeNode) {
    if (savingNodeId === node.id) {
      return;
    }
    setSavingNodeId(node.id);
    try {
      await onRenameAlias(node, editingValue);
      setEditingNodeId(null);
      setEditingValue("");
    } catch (error) {
      console.error("Failed to rename sidebar alias", error);
    } finally {
      setSavingNodeId(null);
    }
  }

  function handleContextMenu(event: ReactMouseEvent<HTMLElement>, node: MarkdownTreeNode) {
    if (!canRenameNode(node)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({
      nodeId: node.id,
      x: Math.max(12, event.clientX),
      y: Math.max(12, event.clientY),
    });
  }

  async function handleDrop(targetNode: TreeRenderNode) {
    if (!draggingNodeId || draggingNodeId === targetNode.id || !dragOver || dragOver.nodeId !== targetNode.id) {
      setDraggingNodeId(null);
      setDragOver(null);
      return;
    }

    if (!findNode(fullTree, draggingNodeId)) {
      setDraggingNodeId(null);
      setDragOver(null);
      return;
    }

    const siblings = findSiblings(fullTree, targetNode.parentId);
    if (!siblings) {
      setDraggingNodeId(null);
      setDragOver(null);
      return;
    }

    const sourceIndex = siblings.findIndex((node) => node.id === draggingNodeId);
    const targetIndex = siblings.findIndex((node) => node.id === targetNode.id);
    if (sourceIndex < 0 || targetIndex < 0) {
      setDraggingNodeId(null);
      setDragOver(null);
      return;
    }

    const next = siblings.slice();
    const [moved] = next.splice(sourceIndex, 1);
    const targetIndexAfterRemoval = next.findIndex((node) => node.id === targetNode.id);
    const insertIndex = dragOver.position === "before" ? targetIndexAfterRemoval : targetIndexAfterRemoval + 1;
    next.splice(insertIndex, 0, moved);

    setDraggingNodeId(null);
    setDragOver(null);
    try {
      await onReorderSiblings(targetNode.parentId, next.map((node) => node.id));
    } catch (error) {
      console.error("Failed to reorder sidebar nodes", error);
    }
  }

  function renderTitleInput(node: MarkdownTreeNode) {
    return (
      <input
        className="sidebarTreeNode__titleInput"
        type="text"
        value={editingValue}
        autoFocus
        disabled={savingNodeId === node.id}
        onClick={(event) => event.stopPropagation()}
        onChange={(event) => setEditingValue(event.currentTarget.value)}
        onBlur={() => {
          if (cancelRenameRef.current) {
            cancelRenameRef.current = false;
            return;
          }
          void submitRename(node);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void submitRename(node);
            return;
          }
          if (event.key === "Escape") {
            event.preventDefault();
            cancelRenameRef.current = true;
            setEditingNodeId(null);
            setEditingValue("");
          }
        }}
      />
    );
  }

  function rowDragProps(node: TreeRenderNode) {
    return {
      draggable: true,
      onDragStart: (event: ReactDragEvent<HTMLElement>) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", node.id);
        setDraggingNodeId(node.id);
        setContextMenu(null);
      },
      onDragOver: (event: ReactDragEvent<HTMLElement>) => {
        if (!draggingNodeId || draggingNodeId === node.id) {
          return;
        }
        const sourceNode = findNode(fullTree, draggingNodeId);
        if (!sourceNode) {
          return;
        }
        const sourceParent = findParentId(fullTree, draggingNodeId);
        if (sourceParent !== node.parentId) {
          setDragOver(null);
          return;
        }
        event.preventDefault();
        const rect = event.currentTarget.getBoundingClientRect();
        const position: DropPosition = event.clientY < rect.top + rect.height / 2 ? "before" : "after";
        setDragOver({ nodeId: node.id, position });
      },
      onDragLeave: () => {
        setDragOver((current) => (current?.nodeId === node.id ? null : current));
      },
      onDrop: (event: ReactDragEvent<HTMLElement>) => {
        event.preventDefault();
        void handleDrop(node);
      },
      onDragEnd: () => {
        setDraggingNodeId(null);
        setDragOver(null);
      },
    };
  }

  function renderNode(node: TreeRenderNode) {
    const isLeaf = node.children.length === 0;
    const isActive = node.path !== null && node.path === currentPath;
    const isAncestor = !isActive && hasActiveDescendant(node, currentPath);
    const isExpanded = !collapsedNodeIds.includes(node.id);
    const branchPaths = collectLeafPaths(node);
    const isDragging = draggingNodeId === node.id;
    const isDropTarget = dragOver?.nodeId === node.id;
    const dragClass = `${isDragging ? " is-dragging" : ""}${isDropTarget ? " is-drop-target" : ""}${dragOver?.position === "before" && isDropTarget ? " is-drop-before" : ""}${dragOver?.position === "after" && isDropTarget ? " is-drop-after" : ""}`;

    if (isLeaf && node.path) {
      return (
        <div
          className={`sidebarTreeLeaf${isActive ? " is-active" : ""}${dragClass}`}
          key={node.id}
          data-sidebar-active={isActive ? "true" : undefined}
          data-sidebar-path={node.path}
          style={{ marginLeft: `${node.depth * 16}px` }}
          onContextMenu={(event) => handleContextMenu(event, node)}
          {...rowDragProps(node)}
        >
          {editingNodeId === node.id ? (
            <div className="sidebarTreeLeaf__main">{renderTitleInput(node)}</div>
          ) : (
            <button
              className="sidebarTreeLeaf__main"
              type="button"
              onClick={() => onOpenPath(node.path!, node.title, node.kind)}
            >
              <span className="sidebarTreeLeaf__title">{node.title}</span>
            </button>
          )}

          <button
            className="sidebarTreeLeaf__close"
            type="button"
            aria-label={`Close ${node.title}`}
            onClick={(event) => {
              event.stopPropagation();
              onClosePath(node.path!);
            }}
          >
            x
          </button>
        </div>
      );
    }

    return (
      <div className={`sidebarTreeNode${isExpanded ? "" : " is-collapsed"}`} key={node.id}>
        <div
          className={`sidebarTreeNode__header${isActive ? " is-active" : ""}${isAncestor ? " is-ancestor" : ""}${dragClass}`}
          data-sidebar-active={isActive ? "true" : undefined}
          data-sidebar-path={node.path ?? undefined}
          style={{ marginLeft: `${node.depth * 16}px` }}
          onContextMenu={(event) => handleContextMenu(event, node)}
          {...rowDragProps(node)}
        >
          <button
            className={`sidebarTreeNode__toggle${isExpanded ? " is-open" : ""}`}
            type="button"
            onClick={() => onToggleNode(node.id)}
            aria-label={isExpanded ? `Collapse ${node.title}` : `Expand ${node.title}`}
          >
            <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
              <path
                d="M5.5 3.5 10.5 8l-5 4.5"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.6"
              />
            </svg>
          </button>

          {editingNodeId === node.id ? (
            <div className="sidebarTreeNode__titleButton">{renderTitleInput(node)}</div>
          ) : (
            <button
              className="sidebarTreeNode__titleButton"
              type="button"
              onClick={() => {
                if (node.path) {
                  onOpenPath(node.path, node.title, node.kind);
                  return;
                }

                onToggleNode(node.id);
              }}
            >
              <span className="sidebarTreeNode__title">{node.title}</span>
            </button>
          )}

          {branchPaths.length ? (
            <button
              className="sidebarTreeNode__close"
              type="button"
              aria-label={`Close items in ${node.title}`}
              onClick={(event) => {
                event.stopPropagation();
                onCloseBranch(branchPaths);
              }}
            >
              x
            </button>
          ) : null}
        </div>

        {isExpanded ? <div className="sidebarTreeNode__children">{node.children.map((child) => renderNode(child))}</div> : null}
      </div>
    );
  }

  return (
    <>
      <div className="sidebar__tree">{renderNodes.map((node) => renderNode(node))}</div>
      {contextMenu
        ? createPortal(
            <div
              className="markdown-contextMenu"
              style={{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }}
              role="menu"
              onClick={(event) => event.stopPropagation()}
              onContextMenu={(event) => event.preventDefault()}
            >
              <button
                className="markdown-contextMenu__item"
                type="button"
                role="menuitem"
                onClick={() => {
                  const node = findNode(fullTree, contextMenu.nodeId);
                  if (node) {
                    beginRename(node);
                  }
                }}
              >
                rename alias
              </button>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

function findParentId(nodes: MarkdownTreeNode[], nodeId: string, parentId: string | null = null): string | null {
  for (const node of nodes) {
    if (node.id === nodeId) {
      return parentId;
    }
    const nested = findParentId(node.children, nodeId, node.id);
    if (nested !== null) {
      return nested;
    }
  }
  return null;
}
