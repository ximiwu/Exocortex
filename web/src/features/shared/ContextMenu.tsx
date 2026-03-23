import { createPortal } from "react-dom";
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";

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
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [position, setPosition] = useState<ContextMenuAnchor | null>(null);

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

  useLayoutEffect(() => {
    if (!open || !anchor || typeof window === "undefined" || !menuRef.current) {
      setPosition(null);
      return;
    }

    const viewportPadding = 12;
    const menuBounds = menuRef.current.getBoundingClientRect();
    const maxLeft = Math.max(viewportPadding, window.innerWidth - menuBounds.width - viewportPadding);
    const maxTop = Math.max(viewportPadding, window.innerHeight - menuBounds.height - viewportPadding);

    setPosition({
      x: Math.min(Math.max(viewportPadding, anchor.x), maxLeft),
      y: Math.min(Math.max(viewportPadding, anchor.y), maxTop),
    });
  }, [anchor, children, open]);

  if (!open || !anchor || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      ref={menuRef}
      className="markdown-contextMenu"
      style={{
        left: `${position?.x ?? Math.max(12, anchor.x)}px`,
        top: `${position?.y ?? Math.max(12, anchor.y)}px`,
        visibility: position ? "visible" : "hidden",
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
