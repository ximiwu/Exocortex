import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MarkdownTreeNode } from "../../app/types";
import { MarkdownTree } from "./MarkdownTree";

const ASK_PATH_1 = "group_data/1/tutor_data/3/ask_history/1.md";
const ASK_PATH_2 = "group_data/1/tutor_data/3/ask_history/2.md";

const TREE: MarkdownTreeNode[] = [
  {
    id: "group:1",
    kind: "group",
    title: "Group 1",
    path: "group_data/1/img_explainer_data/enhanced.md",
    children: [
      {
        id: "tutor:1:3:focus",
        kind: "tutor",
        title: "Tutor 3 Focus",
        path: "group_data/1/tutor_data/3/focus.md",
        children: [
          {
            id: "tutor:1:3:history:1",
            kind: "ask",
            title: "Question 1",
            path: ASK_PATH_1,
            children: [],
          },
          {
            id: "tutor:1:3:history:2",
            kind: "ask",
            title: "Question 2",
            path: ASK_PATH_2,
            children: [],
          },
        ],
      },
      {
        id: "tutor:1:4:focus",
        kind: "tutor",
        title: "Tutor 4 Focus",
        path: "group_data/1/tutor_data/4/focus.md",
        children: [],
      },
    ],
  },
];

function renderTree(options: {
  nodes?: MarkdownTreeNode[];
  currentPath?: string | null;
  openPaths?: string[];
  onOpenPath?: ReturnType<typeof vi.fn>;
  onOpenPaths?: ReturnType<typeof vi.fn>;
  onClosePaths?: ReturnType<typeof vi.fn>;
  onLocateInPdf?: ReturnType<typeof vi.fn>;
  onGenerateFlashcard?: ReturnType<typeof vi.fn>;
  onRevealFlashcard?: ReturnType<typeof vi.fn>;
  onDeleteGroup?: ReturnType<typeof vi.fn>;
  onDeleteTutor?: ReturnType<typeof vi.fn>;
  onDeleteAsk?: ReturnType<typeof vi.fn>;
  onRenameAlias?: ReturnType<typeof vi.fn>;
  onReorderSiblings?: ReturnType<typeof vi.fn>;
} = {}) {
  const onOpenPath = options.onOpenPath ?? vi.fn();
  const onOpenPaths = options.onOpenPaths ?? vi.fn();
  const onClosePaths = options.onClosePaths ?? vi.fn();
  const onLocateInPdf = options.onLocateInPdf ?? vi.fn();
  const onGenerateFlashcard = options.onGenerateFlashcard ?? vi.fn(async () => undefined);
  const onRevealFlashcard = options.onRevealFlashcard ?? vi.fn(async () => undefined);
  const onDeleteGroup = options.onDeleteGroup ?? vi.fn(async () => undefined);
  const onDeleteTutor = options.onDeleteTutor ?? vi.fn(async () => undefined);
  const onDeleteAsk = options.onDeleteAsk ?? vi.fn(async () => undefined);
  const onRenameAlias = options.onRenameAlias ?? vi.fn(async () => undefined);
  const onReorderSiblings = options.onReorderSiblings ?? vi.fn(async () => undefined);
  const currentPath = options.currentPath ?? ASK_PATH_1;
  const openPaths = options.openPaths ?? (currentPath ? [currentPath] : []);

  const view = render(
    <MarkdownTree
      hasAsset
      nodes={options.nodes ?? TREE}
      fullTree={options.nodes ?? TREE}
      currentPath={currentPath}
      openPaths={openPaths}
      collapsedNodeIds={[]}
      sidebarTextLineClamp={1}
      sidebarFontSizePx={14}
      onToggleNode={vi.fn()}
      onOpenPath={onOpenPath}
      onOpenPaths={onOpenPaths}
      onClosePaths={onClosePaths}
      onLocateInPdf={onLocateInPdf}
      onGenerateFlashcard={onGenerateFlashcard}
      onRevealFlashcard={onRevealFlashcard}
      onDeleteGroup={onDeleteGroup}
      onDeleteTutor={onDeleteTutor}
      onDeleteAsk={onDeleteAsk}
      onRenameAlias={onRenameAlias}
      onReorderSiblings={onReorderSiblings}
    />,
  );

  return {
    ...view,
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
  };
}

function openContextMenu(label: string) {
  const rawTextNode = document.querySelector(`[data-raw-text="${label}"]`);
  const button = rawTextNode?.closest("button") ?? screen.getByRole("button", { name: label });
  fireEvent.contextMenu(button, {
    clientX: 50,
    clientY: 50,
  });
}

function cloneTree(nodes: MarkdownTreeNode[]): MarkdownTreeNode[] {
  return nodes.map((node) => ({
    ...node,
    children: cloneTree(node.children),
  }));
}

function getSidebarRow(label: string): HTMLElement {
  const rawTextNode = document.querySelector(`[data-raw-text="${label}"]`);
  const row = rawTextNode?.closest(".sidebarTreeNode__header, .sidebarTreeLeaf");
  expect(row).not.toBeNull();
  return row as HTMLElement;
}

describe("MarkdownTree sidebar behavior", () => {
  it("auto-selects rename input text and disables drag while editing", async () => {
    renderTree();

    openContextMenu("Question 1");
    fireEvent.click(screen.getByRole("menuitem", { name: "rename alias" }));

    const input = screen.getByDisplayValue("Question 1") as HTMLInputElement;
    await waitFor(() => {
      expect(input.selectionStart).toBe(0);
      expect(input.selectionEnd).toBe("Question 1".length);
    });

    const row = input.closest(".sidebarTreeLeaf");
    expect(row).not.toBeNull();
    expect(row).toHaveAttribute("draggable", "false");
  });

  it("shows context menu entries for group, tutor, and ask nodes", () => {
    renderTree({ openPaths: [ASK_PATH_1] });

    openContextMenu("Group 1");
    expect(screen.getByRole("menuitem", { name: "close" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "rename alias" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "locate in pdf" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "history ask session" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "gen flashcard" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "reveal flashcard" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "delete" })).toBeInTheDocument();

    fireEvent.click(document.body);
    openContextMenu("Tutor 3 Focus");
    expect(screen.getByRole("menuitem", { name: "history question" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "delete" })).toBeInTheDocument();

    fireEvent.click(document.body);
    openContextMenu("Question 1");
    expect(screen.getByRole("menuitem", { name: "delete" })).toBeInTheDocument();
  });

  it("keeps the context menu open across tree refreshes with the same nodes", () => {
    const initialTree = cloneTree(TREE);
    const view = renderTree({ nodes: initialTree, openPaths: [ASK_PATH_1] });

    openContextMenu("Group 1");
    expect(screen.getByRole("menuitem", { name: "history ask session" })).toBeInTheDocument();

    view.rerender(
      <MarkdownTree
        hasAsset
        nodes={cloneTree(TREE)}
        fullTree={cloneTree(TREE)}
        currentPath={ASK_PATH_1}
        openPaths={[ASK_PATH_1]}
        collapsedNodeIds={[]}
        sidebarTextLineClamp={1}
        sidebarFontSizePx={14}
        onToggleNode={vi.fn()}
        onOpenPath={view.onOpenPath}
        onOpenPaths={view.onOpenPaths}
        onClosePaths={view.onClosePaths}
        onLocateInPdf={view.onLocateInPdf}
        onGenerateFlashcard={view.onGenerateFlashcard}
        onRevealFlashcard={view.onRevealFlashcard}
        onDeleteGroup={view.onDeleteGroup}
        onDeleteTutor={view.onDeleteTutor}
        onDeleteAsk={view.onDeleteAsk}
        onRenameAlias={view.onRenameAlias}
        onReorderSiblings={view.onReorderSiblings}
      />,
    );

    expect(screen.getByRole("menuitem", { name: "history ask session" })).toBeInTheDocument();
  });

  it("runs flashcard generation from the group context menu", () => {
    const { onGenerateFlashcard } = renderTree();

    openContextMenu("Group 1");
    fireEvent.click(screen.getByRole("menuitem", { name: "gen flashcard" }));

    expect(onGenerateFlashcard).toHaveBeenCalledTimes(1);
    expect(onGenerateFlashcard).toHaveBeenCalledWith(1);
  });

  it("reveals flashcard exports from the group context menu", () => {
    const { onRevealFlashcard } = renderTree();

    openContextMenu("Group 1");
    fireEvent.click(screen.getByRole("menuitem", { name: "reveal flashcard" }));

    expect(onRevealFlashcard).toHaveBeenCalledTimes(1);
    expect(onRevealFlashcard).toHaveBeenCalledWith(1);
  });

  it("emphasizes the active leaf path with separate direct-parent and ancestor states", () => {
    renderTree({ openPaths: [ASK_PATH_1] });

    expect(document.querySelectorAll(".sidebarTreeLeaf.is-active")).toHaveLength(1);
    expect(document.querySelectorAll(".sidebarTreeNode__header.is-direct-ancestor")).toHaveLength(1);
    expect(document.querySelectorAll(".sidebarTreeNode__header.is-ancestor")).toHaveLength(1);

    expect(getSidebarRow("Question 1")).toHaveClass("is-active");
    expect(getSidebarRow("Tutor 3 Focus")).toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Tutor 3 Focus")).not.toHaveClass("is-ancestor");
    expect(getSidebarRow("Group 1")).toHaveClass("is-ancestor");
  });

  it("keeps the direct parent emphasized in a two-level tree", () => {
    const twoLevelTree: MarkdownTreeNode[] = [
      {
        id: "group:9",
        kind: "group",
        title: "Group 9",
        path: "group_data/9/img_explainer_data/enhanced.md",
        children: [
          {
            id: "group:9:summary",
            kind: "summary",
            title: "Summary",
            path: "group_data/9/summary.md",
            children: [],
          },
        ],
      },
    ];

    renderTree({
      nodes: twoLevelTree,
      currentPath: "group_data/9/summary.md",
      openPaths: ["group_data/9/summary.md"],
    });

    expect(getSidebarRow("Summary")).toHaveClass("is-active");
    expect(getSidebarRow("Group 9")).toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Group 9")).not.toHaveClass("is-ancestor");
    expect(document.querySelectorAll(".sidebarTreeNode__header.is-direct-ancestor")).toHaveLength(1);
    expect(document.querySelector(".sidebarTreeNode__header.is-ancestor")).toBeNull();
  });

  it("keeps the active branch emphasized when siblings sit between ancestor and selected descendant", () => {
    const siblingBranchTree: MarkdownTreeNode[] = [
      {
        id: "group:11",
        kind: "group",
        title: "Group 11",
        path: "group_data/11/img_explainer_data/enhanced.md",
        children: [
          {
            id: "tutor:11:1:focus",
            kind: "tutor",
            title: "Tutor 1 Focus",
            path: "group_data/11/tutor_data/1/focus.md",
            children: [],
          },
          {
            id: "tutor:11:2:focus",
            kind: "tutor",
            title: "Tutor 2 Focus",
            path: "group_data/11/tutor_data/2/focus.md",
            children: [
              {
                id: "tutor:11:2:history:1",
                kind: "ask",
                title: "Question 11",
                path: "group_data/11/tutor_data/2/ask_history/1.md",
                children: [],
              },
            ],
          },
          {
            id: "tutor:11:3:focus",
            kind: "tutor",
            title: "Tutor 3 Focus",
            path: "group_data/11/tutor_data/3/focus.md",
            children: [],
          },
        ],
      },
    ];

    renderTree({
      nodes: siblingBranchTree,
      currentPath: "group_data/11/tutor_data/2/ask_history/1.md",
      openPaths: ["group_data/11/tutor_data/2/ask_history/1.md"],
    });

    expect(getSidebarRow("Question 11")).toHaveClass("is-active");
    expect(getSidebarRow("Tutor 2 Focus")).toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Group 11")).toHaveClass("is-ancestor");
    expect(getSidebarRow("Tutor 1 Focus")).not.toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Tutor 3 Focus")).not.toHaveClass("is-direct-ancestor");
    expect(document.querySelector(".sidebarTreeNode__children.is-direct-ancestor")).toBeInTheDocument();
    expect(document.querySelector(".sidebarTreeNode__children.is-ancestor")).toBeInTheDocument();
  });

  it("moves active-path emphasis to the newly selected branch", () => {
    const multiBranchTree: MarkdownTreeNode[] = [
      cloneTree(TREE)[0],
      {
        id: "group:2",
        kind: "group",
        title: "Group 2",
        path: "group_data/2/img_explainer_data/enhanced.md",
        children: [
          {
            id: "tutor:2:1:focus",
            kind: "tutor",
            title: "Tutor 1 Focus",
            path: "group_data/2/tutor_data/1/focus.md",
            children: [
              {
                id: "tutor:2:1:history:1",
                kind: "ask",
                title: "Question 3",
                path: "group_data/2/tutor_data/1/ask_history/1.md",
                children: [],
              },
            ],
          },
        ],
      },
    ];

    const view = render(
      <MarkdownTree
        hasAsset
        nodes={multiBranchTree}
        fullTree={multiBranchTree}
        currentPath={ASK_PATH_1}
        openPaths={[ASK_PATH_1, "group_data/2/tutor_data/1/ask_history/1.md"]}
        collapsedNodeIds={[]}
        sidebarTextLineClamp={1}
        sidebarFontSizePx={14}
        onToggleNode={vi.fn()}
        onOpenPath={vi.fn()}
        onOpenPaths={vi.fn()}
        onClosePaths={vi.fn()}
        onLocateInPdf={vi.fn()}
        onGenerateFlashcard={vi.fn(async () => undefined)}
        onRevealFlashcard={vi.fn(async () => undefined)}
        onDeleteGroup={vi.fn(async () => undefined)}
        onDeleteTutor={vi.fn(async () => undefined)}
        onDeleteAsk={vi.fn(async () => undefined)}
        onRenameAlias={vi.fn(async () => undefined)}
        onReorderSiblings={vi.fn(async () => undefined)}
      />,
    );

    expect(getSidebarRow("Tutor 3 Focus")).toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Group 1")).toHaveClass("is-ancestor");
    expect(getSidebarRow("Tutor 1 Focus")).not.toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Group 2")).not.toHaveClass("is-ancestor");

    view.rerender(
      <MarkdownTree
        hasAsset
        nodes={multiBranchTree}
        fullTree={multiBranchTree}
        currentPath="group_data/2/tutor_data/1/ask_history/1.md"
        openPaths={[ASK_PATH_1, "group_data/2/tutor_data/1/ask_history/1.md"]}
        collapsedNodeIds={[]}
        sidebarTextLineClamp={1}
        sidebarFontSizePx={14}
        onToggleNode={vi.fn()}
        onOpenPath={vi.fn()}
        onOpenPaths={vi.fn()}
        onClosePaths={vi.fn()}
        onLocateInPdf={vi.fn()}
        onGenerateFlashcard={vi.fn(async () => undefined)}
        onRevealFlashcard={vi.fn(async () => undefined)}
        onDeleteGroup={vi.fn(async () => undefined)}
        onDeleteTutor={vi.fn(async () => undefined)}
        onDeleteAsk={vi.fn(async () => undefined)}
        onRenameAlias={vi.fn(async () => undefined)}
        onReorderSiblings={vi.fn(async () => undefined)}
      />,
    );

    expect(getSidebarRow("Tutor 3 Focus")).not.toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Group 1")).not.toHaveClass("is-ancestor");
    expect(getSidebarRow("Tutor 1 Focus")).toHaveClass("is-direct-ancestor");
    expect(getSidebarRow("Group 2")).toHaveClass("is-ancestor");
    expect(getSidebarRow("Question 3")).toHaveClass("is-active");
  });

  it("does not apply ancestor emphasis when a parent node is selected directly", () => {
    renderTree({
      currentPath: "group_data/1/tutor_data/3/focus.md",
      openPaths: ["group_data/1/tutor_data/3/focus.md"],
    });

    expect(getSidebarRow("Tutor 3 Focus")).toHaveClass("is-active");
    expect(document.querySelector(".sidebarTreeNode__header.is-direct-ancestor")).toBeNull();
    expect(document.querySelector(".sidebarTreeNode__header.is-ancestor")).toBeNull();
    expect(getSidebarRow("Group 1")).not.toHaveClass("is-ancestor");
  });

  it("closes only open descendant tabs for the selected branch", () => {
    const { onClosePaths } = renderTree({ openPaths: [ASK_PATH_1] });

    openContextMenu("Group 1");
    fireEvent.click(screen.getByRole("menuitem", { name: "close" }));

    expect(onClosePaths).toHaveBeenCalledTimes(1);
    expect(onClosePaths).toHaveBeenCalledWith([ASK_PATH_1]);
  });

  it("supports ask-session history modal select-all/clear-all and open selected", () => {
    const { onOpenPaths } = renderTree();

    openContextMenu("Group 1");
    fireEvent.click(screen.getByRole("menuitem", { name: "history ask session" }));

    const tutor3 = screen.getByLabelText("Tutor 3 Focus") as HTMLInputElement;
    const tutor4 = screen.getByLabelText("Tutor 4 Focus") as HTMLInputElement;
    expect(tutor3.checked).toBe(false);
    expect(tutor4.checked).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "select all" }));
    expect(tutor3.checked).toBe(true);
    expect(tutor4.checked).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "clear all" }));
    expect(tutor3.checked).toBe(false);
    expect(tutor4.checked).toBe(false);

    fireEvent.click(tutor3);
    fireEvent.click(screen.getByRole("button", { name: "open selected" }));

    expect(onOpenPaths).toHaveBeenCalledTimes(1);
    expect(onOpenPaths).toHaveBeenCalledWith([
      {
        path: "group_data/1/tutor_data/3/focus.md",
        title: "Tutor 3 Focus",
        kind: "tutor",
      },
    ]);
  });

  it("supports history-question modal double-click open and multi-select open", () => {
    const { onOpenPath, onOpenPaths } = renderTree();

    openContextMenu("Tutor 3 Focus");
    fireEvent.click(screen.getByRole("menuitem", { name: "history question" }));

    const modal = screen.getByRole("dialog");
    fireEvent.doubleClick(within(modal).getByText("Question 1"));
    expect(onOpenPath).toHaveBeenCalledWith(ASK_PATH_1, "Question 1", "ask");

    fireEvent.click(within(modal).getByLabelText("Question 1"));
    fireEvent.click(within(modal).getByLabelText("Question 2"));
    fireEvent.click(screen.getByRole("button", { name: "open selected" }));

    expect(onOpenPaths).toHaveBeenCalledWith([
      {
        path: ASK_PATH_1,
        title: "Question 1",
        kind: "ask",
      },
      {
        path: ASK_PATH_2,
        title: "Question 2",
        kind: "ask",
      },
    ]);
  });

  it("renders LaTeX in sidebar titles", async () => {
    const latexTree: MarkdownTreeNode[] = [
      {
        ...TREE[0],
        title: "Group $x^2$",
        children: TREE[0].children,
      },
    ];

    const { container } = renderTree({ nodes: latexTree });

    await waitFor(() => {
      expect(container.querySelector(".sidebarTreeNode__title .katex")).toBeInTheDocument();
    });
  });

  it("renders LaTeX in history modal titles", async () => {
    const latexTree: MarkdownTreeNode[] = [
      {
        ...TREE[0],
        title: "Group 1",
        children: [
          {
            ...TREE[0].children[0],
            title: "Tutor $y$ Focus",
          },
          TREE[0].children[1],
        ],
      },
    ];

    const { container } = renderTree({ nodes: latexTree });

    openContextMenu("Group 1");
    fireEvent.click(screen.getByRole("menuitem", { name: "history ask session" }));

    await waitFor(() => {
      expect(container.querySelector(".sidebarHistoryModal__rowTitle .katex")).toBeInTheDocument();
    });
  });
});
