import type { MarkdownContextMenuState } from "../controllers/types";
import { ContextMenu } from "../../shared/ContextMenu";

interface WorkflowMarkdownContextMenuProps {
  menu: MarkdownContextMenuState | null;
  selectedAssetName: string | null;
  currentMarkdownPath: string | null;
  deleteQuestionEnabled: boolean;
  fixLatexRunning: boolean;
  onClose: () => void;
  runAction: (action: () => Promise<void>) => void;
  onShowInfo: () => Promise<void>;
  onShowInitial: () => Promise<void>;
  onFixLatex: () => Promise<void>;
  onReveal: () => Promise<void>;
  onDeleteQuestion: () => void;
}

export function WorkflowMarkdownContextMenu({
  menu,
  selectedAssetName,
  currentMarkdownPath,
  deleteQuestionEnabled,
  fixLatexRunning,
  onClose,
  runAction,
  onShowInfo,
  onShowInitial,
  onFixLatex,
  onReveal,
  onDeleteQuestion,
}: WorkflowMarkdownContextMenuProps) {
  return (
    <ContextMenu anchor={menu} open={Boolean(menu)} onClose={onClose}>
      <button
        className="markdown-contextMenu__item"
        type="button"
        role="menuitem"
        onClick={() => runAction(onShowInfo)}
        disabled={!selectedAssetName}
      >
        show info
      </button>
      <button
        className="markdown-contextMenu__item"
        type="button"
        role="menuitem"
        onClick={() => runAction(onShowInitial)}
        disabled={!selectedAssetName}
      >
        show initial
      </button>
      <button
        className="markdown-contextMenu__item"
        type="button"
        role="menuitem"
        onClick={() => runAction(onFixLatex)}
        disabled={!selectedAssetName || !currentMarkdownPath || fixLatexRunning}
      >
        fix latex
      </button>
      <button
        className="markdown-contextMenu__item"
        type="button"
        role="menuitem"
        onClick={() => runAction(onReveal)}
        disabled={!selectedAssetName || !currentMarkdownPath}
      >
        reveal in explorer
      </button>
      {deleteQuestionEnabled ? (
        <button
          className="markdown-contextMenu__item markdown-contextMenu__item--danger"
          type="button"
          role="menuitem"
          onClick={onDeleteQuestion}
        >
          delete question
        </button>
      ) : null}
    </ContextMenu>
  );
}
