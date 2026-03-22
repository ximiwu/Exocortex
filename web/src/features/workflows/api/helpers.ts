import type { MarkdownTreeNode } from "../../../generated/contracts";

export interface GroupContext {
  groupIdx: number;
}

export interface TutorContext extends GroupContext {
  tutorIdx: number;
}

export function deriveGroupContext(path: string | null): GroupContext | null {
  if (!path) {
    return null;
  }

  const match = path.match(/group_data\/(\d+)/i);
  if (!match) {
    return null;
  }

  return { groupIdx: Number(match[1]) };
}

export function deriveTutorContext(path: string | null): TutorContext | null {
  if (!path) {
    return null;
  }

  const match = path.match(/group_data\/(\d+)\/tutor_data\/(\d+)/i);
  if (!match) {
    return null;
  }

  return {
    groupIdx: Number(match[1]),
    tutorIdx: Number(match[2]),
  };
}

export function isTutorHistoryMarkdown(path: string | null): boolean {
  if (!path) {
    return false;
  }

  return /\/ask_history\/.+\.md$/i.test(path);
}

export function flattenMarkdownTree(nodes: MarkdownTreeNode[]): MarkdownTreeNode[] {
  const result: MarkdownTreeNode[] = [];

  for (const node of nodes) {
    result.push(node);
    result.push(...flattenMarkdownTree(node.children));
  }

  return result;
}

export function documentTitleFromPath(path: string): string {
  const segments = path.split("/").filter(Boolean);
  return segments.at(-1) ?? path;
}

export function findPreferredGroupMarkdownNode(
  nodes: MarkdownTreeNode[],
  groupIdx: number,
): MarkdownTreeNode | null {
  const prefix = `group_data/${groupIdx}/`;
  const groupNodes = flattenMarkdownTree(nodes).filter(
    (node) => typeof node.path === "string" && node.path.startsWith(prefix),
  );

  if (!groupNodes.length) {
    return null;
  }

  const ranked = [...groupNodes].sort((left, right) => scoreGroupPath(right.path) - scoreGroupPath(left.path));
  return ranked[0] ?? null;
}

export function findGroupEnhancedMarkdownNode(
  nodes: MarkdownTreeNode[],
  groupIdx: number,
): MarkdownTreeNode | null {
  const enhancedPath = `group_data/${groupIdx}/img_explainer_data/enhanced.md`;
  return flattenMarkdownTree(nodes).find((node) => node.path === enhancedPath) ?? null;
}

function scoreGroupPath(path: string | null): number {
  if (!path) {
    return -1;
  }

  if (path.endsWith("/img_explainer_data/enhanced.md")) {
    return 100;
  }
  if (path.endsWith("/content.md")) {
    return 90;
  }
  if (path.endsWith("/note_student.md")) {
    return 80;
  }
  if (path.endsWith("/note.md")) {
    return 75;
  }
  if (path.endsWith("/focus.md")) {
    return 70;
  }
  if (path.endsWith("/bugs.md")) {
    return 65;
  }
  if (path.includes("/img_explainer_data/")) {
    return 60;
  }
  if (path.includes("/tutor_data/")) {
    return path.includes("/ask_history/") ? 10 : 50;
  }
  return 40;
}
