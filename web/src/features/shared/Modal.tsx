import { type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  wide?: boolean;
  className?: string;
  labelledBy?: string;
  role?: "dialog" | "alertdialog";
  dismissOnScrim?: boolean;
  onClose?(): void;
  children: ReactNode;
}

export function Modal({
  open,
  wide = false,
  className,
  labelledBy,
  role = "dialog",
  dismissOnScrim = false,
  onClose,
  children,
}: ModalProps) {
  if (!open) {
    return null;
  }

  const classes = ["modal-card", wide ? "modal-card--wide" : null, className]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className="modal-scrim"
      role="presentation"
      onClick={() => {
        if (dismissOnScrim) {
          onClose?.();
        }
      }}
    >
      <div
        className={classes}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        {children}
      </div>
    </div>
  );
}
