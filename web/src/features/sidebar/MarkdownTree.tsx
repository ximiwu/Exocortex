import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent as ReactDragEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";

import { MarkdownTreeNode } from "../../app/types";
import { ContextMenu } from "../shared/ContextMenu";
import { MathText } from "../shared/MathText";
import { Modal } from "../shared/Modal";
import {
  collectGroupTutorFocusEntries,
  collectNodeOpenPaths,
  collectTutorAskEntries,
  findNodeById,
  findNodePathByPath,
  findParentId,
  findSiblings,
  parseAskContextFromNode,
  parseGroupIdxFromNode,
  parseTutorContextFromNode,
  type OpenableTreeNode,
} from "./treeUtils";

type DropPosition = "before" | "after";

interface MarkdownTreeProps {
  hasAsset: boolean;
  nodes: MarkdownTreeNode[];
  fullTree: MarkdownTreeNode[];
  emptyMessage?: string;
  currentPath: string | null;
  openPaths: string[];
  collapsedNodeIds: string[];
  sidebarTextLineClamp: number;
  sidebarFontSizePx: number;
  onToggleNode: (nodeId: string) => void;
  onOpenPath: (path: string, title: string, kind: string) => void;
  onOpenPaths: (nodes: OpenableTreeNode[]) => void;
  onClosePaths: (paths: string[]) => void;
  onLocateInPdf: (groupIdx: number) => Promise<void> | void;
  onGenerateFlashcard: (groupIdx: number) => Promise<void>;
  onRevealFlashcard: (groupIdx: number) => Promise<void>;
  onDeleteGroup: (groupIdx: number, node: MarkdownTreeNode) => Promise<void>;
  onDeleteTutor: (groupIdx: number, tutorIdx: number, node: MarkdownTreeNode) => Promise<void>;
  onDeleteAsk: (groupIdx: number, tutorIdx: number, path: string) => Promise<void>;
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

interface HistoryModalState {
  title: string;
  entries: OpenableTreeNode[];
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

function canRenameNode(node: MarkdownTreeNode): boolean {
  return node.kind === "group" || node.kind === "tutor" || (node.path !== null && node.children.length === 0);
}

export function MarkdownTree({
  hasAsset,
  nodes,
  fullTree,
  emptyMessage,
  currentPath,
  openPaths,
  collapsedNodeIds,
  sidebarTextLineClamp,
  sidebarFontSizePx,
  onToggleNode,
  onOpenPath,
  onOpenPaths,
  onClosePaths,
  onLocateInPdf,
  onGenerateFlashcard,
  onRevealFlashcard,
  onDeleteGroup,
  onDeleteTutor,
  onDeleteAsk,
  onRenameAlias,
  onReorderSiblings,
}: MarkdownTreeProps) {
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [savingNodeId, setSavingNodeId] = useState<string | null>(null);
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<DragOverState | null>(null);
  const [historyModal, setHistoryModal] = useState<HistoryModalState | null>(null);
  const [selectedHistoryPaths, setSelectedHistoryPaths] = useState<string[]>([]);
  const cancelRenameRef = useRef(false);
  const renameInputRef = useRef<HTMLInputElement | null>(null);
  const renderNodes = useMemo(() => buildRenderTree(nodes, null, 0), [nodes]);
  const openPathSet = useMemo(() => new Set(openPaths), [openPaths]);
  const activePathNodes = useMemo(() => findNodePathByPath(fullTree, currentPath), [fullTree, currentPath]);
  const activeNodeId = activePathNodes.length > 0 ? activePathNodes[activePathNodes.length - 1].id : null;
  const directAncestorNodeId = activePathNodes.length > 1 ? activePathNodes[activePathNodes.length - 2].id : null;
  const ancestorNodeIds = useMemo(
    () => new Set(activePathNodes.slice(0, Math.max(0, activePathNodes.length - 2)).map((node) => node.id)),
    [activePathNodes],
  );
  const activeContextNode = contextMenu ? findNodeById(fullTree, contextMenu.nodeId) : null;
  const activeContextOpenPaths = activeContextNode
    ? collectNodeOpenPaths(activeContextNode, openPathSet)
    : [];
  const activeContextGroupIdx = activeContextNode ? parseGroupIdxFromNode(activeContextNode) : null;
  const activeContextTutor = activeContextNode ? parseTutorContextFromNode(activeContextNode) : null;
  const activeContextAsk = activeContextNode ? parseAskContextFromNode(activeContextNode) : null;
  const canCloseContextNode = activeContextOpenPaths.length > 0;

  useEffect(() => {
    setContextMenu(null);
    setEditingNodeId(null);
    setEditingValue("");
    setSavingNodeId(null);
    setDraggingNodeId(null);
    setDragOver(null);
  }, [currentPath]);

  useEffect(() => {
    if (contextMenu && !findNodeById(fullTree, contextMenu.nodeId)) {
      setContextMenu(null);
    }

    if (editingNodeId && !findNodeById(fullTree, editingNodeId)) {
      setEditingNodeId(null);
      setEditingValue("");
      setSavingNodeId(null);
    }

    if (draggingNodeId && !findNodeById(fullTree, draggingNodeId)) {
      setDraggingNodeId(null);
      setDragOver(null);
    }

    if (dragOver && !findNodeById(fullTree, dragOver.nodeId)) {
      setDragOver(null);
    }
  }, [contextMenu, dragOver, draggingNodeId, editingNodeId, fullTree]);

  useEffect(() => {
    if (!editingNodeId || !renameInputRef.current) {
      return;
    }

    renameInputRef.current.focus();
    renameInputRef.current.select();
  }, [editingNodeId]);

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
    const nodeOpenPaths = collectNodeOpenPaths(node, openPathSet);
    const hasNodeActions =
      nodeOpenPaths.length > 0 ||
      canRenameNode(node) ||
      node.kind === "group" ||
      node.kind === "tutor" ||
      node.kind === "ask";
    if (!hasNodeActions) {
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

    if (!findNodeById(fullTree, draggingNodeId)) {
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
        disabled={savingNodeId === node.id}
        ref={renameInputRef}
        onMouseDown={(event) => event.stopPropagation()}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
        onFocus={(event) => event.currentTarget.select()}
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
    const disabled = editingNodeId === node.id;

    return {
      draggable: !disabled,
      onDragStart: (event: ReactDragEvent<HTMLElement>) => {
        if (disabled) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", node.id);
        setDraggingNodeId(node.id);
        setContextMenu(null);
      },
      onDragOver: (event: ReactDragEvent<HTMLElement>) => {
        if (disabled) {
          return;
        }
        if (!draggingNodeId || draggingNodeId === node.id) {
          return;
        }
        const sourceNode = findNodeById(fullTree, draggingNodeId);
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
    const isActive = node.id === activeNodeId;
    const isDirectAncestor = node.id === directAncestorNodeId;
    const isAncestor = ancestorNodeIds.has(node.id);
    const isExpanded = !collapsedNodeIds.includes(node.id);
    const isDragging = draggingNodeId === node.id;
    const isDropTarget = dragOver?.nodeId === node.id;
    const dragClass = `${isDragging ? " is-dragging" : ""}${isDropTarget ? " is-drop-target" : ""}${dragOver?.position === "before" && isDropTarget ? " is-drop-before" : ""}${dragOver?.position === "after" && isDropTarget ? " is-drop-after" : ""}`;
    const indentStyle = {
      "--sidebar-node-indent": `${node.depth * 16}px`,
    } as CSSProperties;

    if (isLeaf && node.path) {
      return (
        <div
          className={`sidebarTreeLeaf${isActive ? " is-active" : ""}${isDirectAncestor ? " is-direct-ancestor" : ""}${isAncestor ? " is-ancestor" : ""}${dragClass}`}
          key={node.id}
          data-sidebar-active={isActive ? "true" : undefined}
          data-sidebar-path={node.path}
          style={indentStyle}
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
              <MathText className="sidebarTreeLeaf__title" text={node.title} />
            </button>
          )}
        </div>
      );
    }

    return (
      <div
        className={`sidebarTreeNode${isExpanded ? "" : " is-collapsed"}${isDirectAncestor || isAncestor ? " has-active-branch" : ""}${isDirectAncestor ? " is-direct-ancestor" : ""}${isAncestor ? " is-ancestor" : ""}`}
        key={node.id}
        style={indentStyle}
      >
        <div
          className={`sidebarTreeNode__header${isActive ? " is-active" : ""}${isDirectAncestor ? " is-direct-ancestor" : ""}${isAncestor ? " is-ancestor" : ""}${dragClass}`}
          data-sidebar-active={isActive ? "true" : undefined}
          data-sidebar-path={node.path ?? undefined}
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
              <MathText className="sidebarTreeNode__title" text={node.title} />
            </button>
          )}
        </div>

        {isExpanded ? (
          <div
            className={`sidebarTreeNode__children${isDirectAncestor || isAncestor ? " is-active-branch" : ""}${isDirectAncestor ? " is-direct-ancestor" : ""}${isAncestor ? " is-ancestor" : ""}`}
          >
            {node.children.map((child) => renderNode(child))}
          </div>
        ) : null}
      </div>
    );
  }

  async function runContextAction(action: () => Promise<void> | void) {
    setContextMenu(null);
    try {
      await action();
    } catch (error) {
      console.error("Sidebar context action failed", error);
    }
  }

  function openHistoryModal(entries: OpenableTreeNode[], title: string) {
    setHistoryModal({
      title,
      entries,
    });
    setSelectedHistoryPaths([]);
  }

  const allHistorySelected = historyModal
    ? historyModal.entries.length > 0 && selectedHistoryPaths.length === historyModal.entries.length
    : false;

  const treeStyle = {
    "--sidebar-node-line-clamp": String(Math.max(1, Math.min(6, Math.floor(sidebarTextLineClamp)))),
    "--sidebar-node-font-size": `${Math.max(10, Math.min(24, Math.floor(sidebarFontSizePx)))}px`,
  } as CSSProperties;

  return (
    <>
      <div className="sidebar__tree" style={treeStyle}>
        {renderNodes.map((node) => renderNode(node))}
      </div>
      <ContextMenu
        anchor={contextMenu}
        open={contextMenu !== null}
        onClose={() => {
          setContextMenu(null);
        }}
      >
        {canCloseContextNode ? (
          <button
            className="markdown-contextMenu__item markdown-contextMenu__item--danger"
            type="button"
            role="menuitem"
            onClick={() => {
              if (!activeContextNode || !activeContextOpenPaths.length) {
                return;
              }

              void runContextAction(() => {
                onClosePaths(activeContextOpenPaths);
              });
            }}
          >
            close
          </button>
        ) : null}
        {activeContextNode && canRenameNode(activeContextNode) ? (
          <button
            className="markdown-contextMenu__item"
            type="button"
            role="menuitem"
            onClick={() => {
              if (!activeContextNode) {
                return;
              }

              beginRename(activeContextNode);
            }}
          >
            rename alias
          </button>
        ) : null}
        {activeContextNode?.kind === "group" && activeContextGroupIdx !== null ? (
          <>
            <button
              className="markdown-contextMenu__item"
              type="button"
              role="menuitem"
              onClick={() => {
                void runContextAction(() => onLocateInPdf(activeContextGroupIdx));
              }}
            >
              locate in pdf
            </button>
            <button
              className="markdown-contextMenu__item"
              type="button"
              role="menuitem"
              onClick={() => {
                const entries = collectGroupTutorFocusEntries(activeContextNode);
                setContextMenu(null);
                openHistoryModal(entries, "history ask session");
              }}
            >
              history ask session
            </button>
            <button
              className="markdown-contextMenu__item"
              type="button"
              role="menuitem"
              onClick={() => {
                void runContextAction(() => onGenerateFlashcard(activeContextGroupIdx));
              }}
            >
              gen flashcard
            </button>
            <button
              className="markdown-contextMenu__item"
              type="button"
              role="menuitem"
              onClick={() => {
                void runContextAction(() => onRevealFlashcard(activeContextGroupIdx));
              }}
            >
              reveal flashcard
            </button>
            <button
              className="markdown-contextMenu__item markdown-contextMenu__item--danger"
              type="button"
              role="menuitem"
              onClick={() => {
                if (
                  !activeContextNode ||
                  activeContextGroupIdx === null ||
                  typeof window !== "undefined" &&
                    !window.confirm(`Delete ${activeContextNode.title}?`)
                ) {
                  return;
                }

                void runContextAction(() => onDeleteGroup(activeContextGroupIdx, activeContextNode));
              }}
            >
              delete
            </button>
          </>
        ) : null}
        {activeContextNode?.kind === "tutor" && activeContextTutor !== null ? (
          <>
            <button
              className="markdown-contextMenu__item"
              type="button"
              role="menuitem"
              onClick={() => {
                const entries = collectTutorAskEntries(activeContextNode);
                setContextMenu(null);
                openHistoryModal(entries, "history question");
              }}
            >
              history question
            </button>
            <button
              className="markdown-contextMenu__item markdown-contextMenu__item--danger"
              type="button"
              role="menuitem"
              onClick={() => {
                if (
                  !activeContextNode ||
                  typeof window !== "undefined" &&
                    !window.confirm(`Delete ${activeContextNode.title}?`)
                ) {
                  return;
                }

                void runContextAction(() =>
                  onDeleteTutor(activeContextTutor.groupIdx, activeContextTutor.tutorIdx, activeContextNode),
                );
              }}
            >
              delete
            </button>
          </>
        ) : null}
        {activeContextNode?.kind === "ask" && activeContextAsk !== null && activeContextNode.path ? (
          <button
            className="markdown-contextMenu__item markdown-contextMenu__item--danger"
            type="button"
            role="menuitem"
            onClick={() => {
              if (
                !activeContextNode.path ||
                typeof window !== "undefined" &&
                  !window.confirm(`Delete ${activeContextNode.title}?`)
              ) {
                return;
              }

              void runContextAction(() =>
                onDeleteAsk(activeContextAsk.groupIdx, activeContextAsk.tutorIdx, activeContextNode.path!),
              );
            }}
          >
            delete
          </button>
        ) : null}
      </ContextMenu>
      <Modal
        open={historyModal !== null}
        onClose={() => {
          setHistoryModal(null);
          setSelectedHistoryPaths([]);
        }}
        labelledBy="sidebar-history-modal-title"
      >
        <div className="sidebarHistoryModal">
          <h2 id="sidebar-history-modal-title" className="sidebarHistoryModal__title">
            {historyModal?.title ?? "history"}
          </h2>
          <div className="sidebarHistoryModal__list" role="list">
            {(historyModal?.entries ?? []).map((entry) => {
              const selected = selectedHistoryPaths.includes(entry.path);
              return (
                <label
                  className="sidebarHistoryModal__row"
                  key={entry.path}
                  role="listitem"
                  onDoubleClick={() => {
                    onOpenPath(entry.path, entry.title, entry.kind);
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => {
                      setSelectedHistoryPaths((current) =>
                        current.includes(entry.path)
                          ? current.filter((path) => path !== entry.path)
                          : [...current, entry.path],
                      );
                    }}
                  />
                  <MathText className="sidebarHistoryModal__rowTitle" text={entry.title} />
                </label>
              );
            })}
            {historyModal?.entries.length ? null : (
              <p className="sidebarHistoryModal__empty">No history entries are available.</p>
            )}
          </div>
          <div className="modal-actions">
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                if (!historyModal) {
                  return;
                }

                setSelectedHistoryPaths(
                  allHistorySelected ? [] : historyModal.entries.map((entry) => entry.path),
                );
              }}
              disabled={!historyModal?.entries.length}
            >
              {allHistorySelected ? "clear all" : "select all"}
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                setHistoryModal(null);
                setSelectedHistoryPaths([]);
              }}
            >
              cancel
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                if (!historyModal || !selectedHistoryPaths.length) {
                  return;
                }

                const selectedEntries = historyModal.entries.filter((entry) =>
                  selectedHistoryPaths.includes(entry.path),
                );
                onOpenPaths(selectedEntries);
                setHistoryModal(null);
                setSelectedHistoryPaths([]);
              }}
              disabled={!selectedHistoryPaths.length}
            >
              open selected
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
