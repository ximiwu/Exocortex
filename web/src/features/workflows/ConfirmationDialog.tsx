import { Modal } from "../shared/Modal";

interface ConfirmationDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "neutral" | "danger";
  busy?: boolean;
  onCancel(): void;
  onConfirm(): void;
}

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = "cancel",
  tone = "neutral",
  busy = false,
  onCancel,
  onConfirm
}: ConfirmationDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <Modal open={open} labelledBy="dialog-title">
      <div>
        <p className="section-kicker">Confirmation</p>
        <h2 id="dialog-title">{title}</h2>
        <p className="modal-copy">{description}</p>
        <div className="modal-actions">
          <button className="ghost-button" type="button" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button
            className={`primary-button ${tone === "danger" ? "primary-button--danger" : ""}`}
            type="button"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "working..." : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
