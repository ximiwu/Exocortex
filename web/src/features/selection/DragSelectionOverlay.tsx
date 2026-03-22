import type { CSSProperties, ReactElement } from "react";

import type { SelectionRect } from "./selectionGeometry";

interface DragSelectionOverlayProps {
  rect: SelectionRect | null;
}

export function DragSelectionOverlay({
  rect,
}: DragSelectionOverlayProps): ReactElement | null {
  if (!rect) {
    return null;
  }

  const style: CSSProperties = {
    left: rect.x,
    top: rect.y,
    width: rect.width,
    height: rect.height,
  };

  return <div className="selection-overlay" style={style} />;
}
