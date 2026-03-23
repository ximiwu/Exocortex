import type { AssetState, MarkdownTreeNode } from "../../app/types";

export interface OpenableTreeNode {
  path: string;
  title: string;
  kind: string;
}

export function collectLeafPaths(node: MarkdownTreeNode): string[] {
  const ownPath = node.path ? [node.path] : [];
  return [...ownPath, ...node.children.flatMap(collectLeafPaths)];
}

export function filterTreeByPaths(
  nodes: MarkdownTreeNode[],
  openPaths: Set<string>,
): MarkdownTreeNode[] {
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

export function findNodeById(
  nodes: MarkdownTreeNode[],
  nodeId: string,
): MarkdownTreeNode | null {
  for (const node of nodes) {
    if (node.id === nodeId) {
      return node;
    }

    const child = findNodeById(node.children, nodeId);
    if (child) {
      return child;
    }
  }

  return null;
}

export function findParentId(
  nodes: MarkdownTreeNode[],
  nodeId: string,
  parentId: string | null = null,
): string | null {
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

export function findSiblings(
  nodes: MarkdownTreeNode[],
  parentId: string | null,
): MarkdownTreeNode[] | null {
  if (parentId === null) {
    return nodes;
  }

  return findNodeById(nodes, parentId)?.children ?? null;
}

export function flattenOpenableNodes(nodes: MarkdownTreeNode[]): OpenableTreeNode[] {
  const result: OpenableTreeNode[] = [];

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

export function hasActiveDescendant(
  node: MarkdownTreeNode,
  currentPath: string | null,
): boolean {
  if (!currentPath) {
    return false;
  }

  if (node.path === currentPath) {
    return true;
  }

  return node.children.some((child) => hasActiveDescendant(child, currentPath));
}

export function collectNodeOpenPaths(node: MarkdownTreeNode, openPaths: Set<string>): string[] {
  const leafPaths = collectLeafPaths(node);
  const matched: string[] = [];

  for (const path of leafPaths) {
    if (openPaths.has(path) && !matched.includes(path)) {
      matched.push(path);
    }
  }

  return matched;
}

export function parseGroupIdxFromNode(node: MarkdownTreeNode): number | null {
  const fromId = node.id.match(/^group:(\d+)$/);
  if (fromId) {
    return Number(fromId[1]);
  }

  const fromPath = node.path?.match(/group_data\/(\d+)/i);
  if (fromPath) {
    return Number(fromPath[1]);
  }

  return null;
}

export interface TutorPathContext {
  groupIdx: number;
  tutorIdx: number;
}

export function parseTutorContextFromNode(node: MarkdownTreeNode): TutorPathContext | null {
  const fromId = node.id.match(/^tutor:(\d+):(\d+):focus$/);
  if (fromId) {
    return {
      groupIdx: Number(fromId[1]),
      tutorIdx: Number(fromId[2]),
    };
  }

  const fromPath = node.path?.match(/group_data\/(\d+)\/tutor_data\/(\d+)/i);
  if (fromPath) {
    return {
      groupIdx: Number(fromPath[1]),
      tutorIdx: Number(fromPath[2]),
    };
  }

  return null;
}

export function parseAskContextFromNode(node: MarkdownTreeNode): TutorPathContext | null {
  const fromId = node.id.match(/^tutor:(\d+):(\d+):history:[^:]+$/);
  if (fromId) {
    return {
      groupIdx: Number(fromId[1]),
      tutorIdx: Number(fromId[2]),
    };
  }

  const fromPath = node.path?.match(/group_data\/(\d+)\/tutor_data\/(\d+)\/ask_history\/.+\.md$/i);
  if (fromPath) {
    return {
      groupIdx: Number(fromPath[1]),
      tutorIdx: Number(fromPath[2]),
    };
  }

  return null;
}

export function collectGroupTutorFocusEntries(node: MarkdownTreeNode): OpenableTreeNode[] {
  return node.children
    .filter((child) => child.kind === "tutor" && Boolean(child.path))
    .map((child) => ({
      path: child.path!,
      title: child.title,
      kind: child.kind,
    }));
}

export function collectTutorAskEntries(node: MarkdownTreeNode): OpenableTreeNode[] {
  return node.children
    .filter((child) => child.kind === "ask" && Boolean(child.path))
    .map((child) => ({
      path: child.path!,
      title: child.title,
      kind: child.kind,
    }));
}

export function resolveLocatePageIndex(assetState: AssetState | null, groupIdx: number): number | null {
  if (!assetState) {
    return null;
  }

  const targetGroup = assetState.groups.find((group) => group.groupIdx === groupIdx) ?? null;
  const firstBlockId = targetGroup?.blockIds[0] ?? null;
  if (!firstBlockId) {
    return null;
  }

  const block = assetState.blocks.find((candidate) => candidate.blockId === firstBlockId) ?? null;
  return block?.pageIndex ?? null;
}
