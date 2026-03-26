import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AppStoreState } from "../store/appStore";
import { useAppStore } from "../store/appStore";
import type { WorkflowCommandController } from "../../features/workflows/controllers/useWorkflowCommandController";
import { WorkbenchShell } from "./WorkbenchShell";

const workflowControllerMock = {
  apiMode: "mock",
  tutorAskVisible: false,
  selectedAssetName: null as string | null,
  currentMarkdownPath: null,
  markdownTree: [],
  effectiveGroupIdx: null,
  effectiveTutorIdx: null,
  questionText: "",
  pendingImportIntent: null,
  feynman: null,
  markdownContextMenu: null,
  deleteQuestionEnabled: false,
  activeTaskPanel: false,
  importDialogOpen: false,
  importSubmitting: false,
  importError: null,
  confirmation: null,
  confirmationBusy: false,
  compressPreview: null,
  setPendingImportIntent: vi.fn(),
  setCompressPreview: vi.fn(),
  setFeynman: vi.fn(),
  setActiveTaskPanel: vi.fn(),
  setImportDialogOpen: vi.fn(),
  closeMarkdownContextMenu: vi.fn(),
  runMarkdownContextAction: vi.fn(),
  handleShowInfo: vi.fn(),
  handleShowInitial: vi.fn(),
  handleFixLatex: vi.fn(),
  handleReveal: vi.fn(),
  openDeleteQuestionConfirmation: vi.fn(),
  handleAskTutor: vi.fn(),
  setQuestionText: vi.fn(),
  closeImportDialog: vi.fn(),
  handleImportSubmit: vi.fn(),
  closeConfirmation: vi.fn(),
  confirmAction: vi.fn(),
} satisfies WorkflowCommandController;

vi.mock("../../features/sidebar/AssetPickerOverlay", () => ({
  AssetPickerOverlay: () => <div data-testid="asset-picker-overlay" />,
}));

vi.mock("../../features/sidebar/SidebarPane", () => ({
  SidebarPane: () => <div data-testid="sidebar-pane" />,
}));

vi.mock("../../features/markdown/MarkdownWorkspace", () => ({
  MarkdownWorkspace: () => <div data-testid="markdown-workspace" />,
}));

vi.mock("../../features/pdf", () => ({
  PdfPaneContainer: ({ toolbarSlot }: { toolbarSlot?: ReactNode }) => (
    <div data-testid="pdf-pane-container">
      {toolbarSlot}
    </div>
  ),
}));

vi.mock("../../features/tasks/TaskCenterContext", () => ({
  useTaskCenter: () => ({
    isTaskRunning: () => false,
  }),
}));

vi.mock("../../features/workflows/components/WorkflowMarkdownContextMenu", () => ({
  WorkflowMarkdownContextMenu: () => null,
}));

vi.mock("../../features/workflows/components/WorkflowModalHost", () => ({
  WorkflowModalHost: () => null,
}));

vi.mock("../../features/workflows/components/WorkflowTutorDock", () => ({
  WorkflowTutorDock: () => null,
}));

vi.mock("../../features/workflows/controllers/useWorkflowCommandController", () => ({
  useWorkflowCommandController: () => workflowControllerMock,
}));

vi.mock("../../features/workflows/controllers/useWorkflowTaskEffectsBridge", () => ({
  useWorkflowTaskEffectsBridge: () => undefined,
}));

vi.mock("../../features/workflows/api/helpers", () => ({
  findGroupEnhancedMarkdownNode: () => null,
}));

vi.mock("./desktopShell", () => ({
  useDesktopShell: () => ({
    isDesktopShell: false,
    isMaximized: false,
    minimize: vi.fn(async () => undefined),
    toggleMaximize: vi.fn(async () => undefined),
    close: vi.fn(async () => undefined),
  }),
}));

const INITIAL_STORE_STATE = useAppStore.getState();

function resetStore(overrides: Partial<AppStoreState> = {}) {
  useAppStore.setState(
    {
      ...INITIAL_STORE_STATE,
      theme: "light",
      selectedAssetName: "asset-a",
      sidebarCollapsed: false,
      sidebarWidthRatio: 0.2,
      rightRailWidthRatio: 0.25,
      appMode: "normal",
      compressSelection: null,
      ...overrides,
    },
    true,
  );
}

function installDesktopMediaMocks() {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: 1600,
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function installPointerCaptureMocks() {
  const capturedPointers = new WeakMap<HTMLElement, Set<number>>();

  Object.defineProperty(HTMLElement.prototype, "setPointerCapture", {
    configurable: true,
    value(pointerId: number) {
      const current = capturedPointers.get(this) ?? new Set<number>();
      current.add(pointerId);
      capturedPointers.set(this, current);
    },
  });

  Object.defineProperty(HTMLElement.prototype, "releasePointerCapture", {
    configurable: true,
    value(pointerId: number) {
      capturedPointers.get(this)?.delete(pointerId);
    },
  });

  Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
    configurable: true,
    value(pointerId: number) {
      return capturedPointers.get(this)?.has(pointerId) ?? false;
    },
  });
}

function dispatchWindowPointerEvent(type: string, clientX: number) {
  const event = new Event(type);
  Object.defineProperty(event, "clientX", {
    configurable: true,
    value: clientX,
  });
  window.dispatchEvent(event);
}

describe("WorkbenchShell pane dragging", () => {
  beforeEach(() => {
    installDesktopMediaMocks();
    installPointerCaptureMocks();
    vi.stubGlobal(
      "ResizeObserver",
      class ResizeObserver {
        observe() {}

        disconnect() {}
      },
    );
    resetStore();
  });

  afterEach(() => {
    cleanup();
    Object.assign(workflowControllerMock, {
      tutorAskVisible: false,
      selectedAssetName: null,
      effectiveGroupIdx: null,
      effectiveTutorIdx: null,
      questionText: "",
      pendingImportIntent: null,
      feynman: null,
      markdownContextMenu: null,
      deleteQuestionEnabled: false,
      activeTaskPanel: false,
      importDialogOpen: false,
      importSubmitting: false,
      importError: null,
      confirmation: null,
      confirmationBusy: false,
      compressPreview: null,
    });
    workflowControllerMock.setPendingImportIntent.mockClear();
    workflowControllerMock.setCompressPreview.mockClear();
    workflowControllerMock.setFeynman.mockClear();
    workflowControllerMock.setActiveTaskPanel.mockClear();
    workflowControllerMock.setImportDialogOpen.mockClear();
    workflowControllerMock.closeMarkdownContextMenu.mockClear();
    workflowControllerMock.runMarkdownContextAction.mockClear();
    workflowControllerMock.handleShowInfo.mockClear();
    workflowControllerMock.handleShowInitial.mockClear();
    workflowControllerMock.handleFixLatex.mockClear();
    workflowControllerMock.handleReveal.mockClear();
    workflowControllerMock.openDeleteQuestionConfirmation.mockClear();
    workflowControllerMock.handleAskTutor.mockClear();
    workflowControllerMock.setQuestionText.mockClear();
    workflowControllerMock.closeImportDialog.mockClear();
    workflowControllerMock.handleImportSubmit.mockClear();
    workflowControllerMock.closeConfirmation.mockClear();
    workflowControllerMock.confirmAction.mockClear();
    useAppStore.setState(INITIAL_STORE_STATE, true);
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("keeps manual workflow button behavior", async () => {
    workflowControllerMock.selectedAssetName = "asset-a";

    render(
      <WorkbenchShell
        assets={[]}
        markdownTree={[]}
        dataSource="mock"
        assetsLoading={false}
        assetsError={null}
        treeLoading={false}
        treeError={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "workflow" }));

    expect(workflowControllerMock.setActiveTaskPanel).toHaveBeenCalledWith(true);
  });

  it("updates the DOM preview during pointermove but commits the right-rail ratio only on pointerup", async () => {
    const setRightRailWidthRatio = vi.fn();
    resetStore({ setRightRailWidthRatio });

    const { container } = render(
      <WorkbenchShell
        assets={[]}
        markdownTree={[]}
        dataSource="mock"
        assetsLoading={false}
        assetsError={null}
        treeLoading={false}
        treeError={null}
      />,
    );

    const workspace = container.querySelector(".shell__workspace--desktop") as HTMLElement | null;
    expect(workspace).not.toBeNull();
    Object.defineProperty(workspace!, "getBoundingClientRect", {
      configurable: true,
      value: () => ({
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: 1400,
        bottom: 900,
        width: 1400,
        height: 900,
        toJSON: () => ({}),
      }),
    });

    await waitFor(() => {
      expect(workspace?.style.gridTemplateColumns).not.toBe("");
    });

    const initialTemplate = workspace!.style.gridTemplateColumns;
    const splitter = screen.getByRole("separator", { name: "Resize markdown and PDF panes" });

    fireEvent.pointerDown(splitter, { clientX: 900 });
    dispatchWindowPointerEvent("pointermove", 700);

    expect(workspace!.style.gridTemplateColumns).not.toBe(initialTemplate);
    expect(setRightRailWidthRatio).not.toHaveBeenCalled();

    dispatchWindowPointerEvent("pointerup", 700);

    expect(setRightRailWidthRatio).toHaveBeenCalledTimes(1);
    const committedRatio = setRightRailWidthRatio.mock.calls[0]?.[0];
    expect(committedRatio).toBeGreaterThan(0.25);
    expect(committedRatio).toBeLessThan(0.8);
  });

  it("reverts the preview without committing when a drag is cancelled", async () => {
    const setRightRailWidthRatio = vi.fn();
    resetStore({ setRightRailWidthRatio });

    const { container } = render(
      <WorkbenchShell
        assets={[]}
        markdownTree={[]}
        dataSource="mock"
        assetsLoading={false}
        assetsError={null}
        treeLoading={false}
        treeError={null}
      />,
    );

    const workspace = container.querySelector(".shell__workspace--desktop") as HTMLElement | null;
    expect(workspace).not.toBeNull();
    Object.defineProperty(workspace!, "getBoundingClientRect", {
      configurable: true,
      value: () => ({
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: 1400,
        bottom: 900,
        width: 1400,
        height: 900,
        toJSON: () => ({}),
      }),
    });

    await waitFor(() => {
      expect(workspace?.style.gridTemplateColumns).not.toBe("");
    });

    const initialTemplate = workspace!.style.gridTemplateColumns;
    const splitter = screen.getByRole("separator", { name: "Resize markdown and PDF panes" });

    fireEvent.pointerDown(splitter, { clientX: 900 });
    dispatchWindowPointerEvent("pointermove", 760);
    expect(workspace!.style.gridTemplateColumns).not.toBe(initialTemplate);

    window.dispatchEvent(new Event("pointercancel"));

    expect(setRightRailWidthRatio).not.toHaveBeenCalled();
    expect(workspace!.style.gridTemplateColumns).toBe(initialTemplate);
  });

  it("clears the global no-select state when the window loses focus during a drag", async () => {
    const { container } = render(
      <WorkbenchShell
        assets={[]}
        markdownTree={[]}
        dataSource="mock"
        assetsLoading={false}
        assetsError={null}
        treeLoading={false}
        treeError={null}
      />,
    );

    const workspace = container.querySelector(".shell__workspace--desktop") as HTMLElement | null;
    expect(workspace).not.toBeNull();
    Object.defineProperty(workspace!, "getBoundingClientRect", {
      configurable: true,
      value: () => ({
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: 1400,
        bottom: 900,
        width: 1400,
        height: 900,
        toJSON: () => ({}),
      }),
    });

    await waitFor(() => {
      expect(workspace?.style.gridTemplateColumns).not.toBe("");
    });

    const splitter = screen.getByRole("separator", { name: "Resize markdown and PDF panes" });

    fireEvent.pointerDown(splitter, { clientX: 900, pointerId: 7 });
    expect(document.body.classList.contains("is-resizing-panes")).toBe(true);

    window.dispatchEvent(new Event("blur"));

    expect(document.body.classList.contains("is-resizing-panes")).toBe(false);
  });
});
