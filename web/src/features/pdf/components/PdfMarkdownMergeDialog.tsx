import type { FormEvent } from "react";

import { Modal } from "../../shared/Modal";

interface PdfMarkdownMergeDialogProps {
  open: boolean;
  busy: boolean;
  markdown: string;
  error?: string | null;
  onMarkdownChange: (value: string) => void;
  onClose: () => void;
  onConfirm: () => void;
}

export function PdfMarkdownMergeDialog({
  open,
  busy,
  markdown,
  error = null,
  onMarkdownChange,
  onClose,
  onConfirm,
}: PdfMarkdownMergeDialogProps) {
  if (!open) {
    return null;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onConfirm();
  }

  return (
    <Modal
      open={open}
      wide
      className="pdf-pane__markdownDialog"
      dismissOnScrim={!busy}
      onClose={onClose}
    >
      <form
        onClick={(event) => {
          event.stopPropagation();
        }}
        onSubmit={handleSubmit}
      >
        <h2>Merge</h2>
        <p className="modal-copy">
          Review or edit the generated markdown for the new group. Confirming will merge the selected blocks and
          save the result to <code>content.md</code>.
        </p>
        {error ? <p className="pdf-pane__markdownError">{error}</p> : null}
        <label className="form-field">
          <span>Markdown</span>
          <textarea
            autoFocus
            className="pdf-pane__markdownInput"
            disabled={busy}
            onChange={(event) => {
              onMarkdownChange(event.target.value);
            }}
            rows={12}
            value={markdown}
          />
        </label>
        <div className="modal-actions">
          <button
            className="pdf-pane__button pdf-pane__button--secondary"
            disabled={busy}
            onClick={() => {
              if (!busy) {
                onClose();
              }
            }}
            type="button"
          >
            Cancel
          </button>
          <button className="pdf-pane__button" disabled={busy} type="submit">
            Confirm
          </button>
        </div>
      </form>
    </Modal>
  );
}
