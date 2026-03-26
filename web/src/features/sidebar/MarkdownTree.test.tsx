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

  const view = render(
    <MarkdownTree
      hasAsset
      nodes={options.nodes ?? TREE}
      fullTree={options.nodes ?? TREE}
      currentPath={ASK_PATH_1}
      openPaths={options.openPaths ?? [ASK_PATH_1]}
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
