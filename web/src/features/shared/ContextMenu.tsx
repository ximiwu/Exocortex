import { createPortal } from "react-dom";
import { type ReactNode, useEffect } from "react";

interface ContextMenuAnchor {
  x: number;
  y: number;
}

interface ContextMenuProps {
  anchor: ContextMenuAnchor | null;
  open: boolean;
  onClose(): void;
  children: ReactNode;
}

export function ContextMenu({
  anchor,
  open,
  onClose,
  children,
}: ContextMenuProps) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const closeMenu = () => {
      onClose();
    };

    window.addEventListener("click", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("keydown", closeMenu);
    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("keydown", closeMenu);
    };
  }, [onClose, open]);

  if (!open || !anchor || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      className="markdown-contextMenu"
      style={{
        left: `${Math.max(12, anchor.x)}px`,
        top: `${Math.max(12, anchor.y)}px`,
      }}
      role="menu"
      onClick={(event) => {
        event.stopPropagation();
      }}
      onContextMenu={(event) => {
        event.preventDefault();
      }}
    >
      {children}
    </div>,
    document.body,
  );
}
