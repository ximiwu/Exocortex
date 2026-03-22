import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import {
  clampPointToBounds,
  clampRectToBounds,
  isRectLargeEnough,
  rectFromPoints,
  type SelectionPoint,
  type SelectionRect,
  type SelectionSize,
} from "./selectionGeometry";

interface DragSession {
  pointerId: number;
  pageIndex: number;
  bounds: SelectionSize;
  origin: SelectionPoint;
  current: SelectionPoint;
}

export interface DragSelectionResult {
  pageIndex: number;
  rect: SelectionRect;
  bounds: SelectionSize;
}

interface UseDragSelectionOptions {
  enabled?: boolean;
  minimumSize?: number;
  onSelectionCommit: (selection: DragSelectionResult) => void;
}

export function useDragSelection({
  enabled = true,
  minimumSize = 4,
  onSelectionCommit,
}: UseDragSelectionOptions) {
  const sessionRef = useRef<DragSession | null>(null);
  const [session, setSession] = useState<DragSession | null>(null);

  function beginDrag(
    event: ReactPointerEvent<HTMLElement>,
    pageIndex: number,
  ): void {
    if (!enabled || event.button !== 0) {
      return;
    }

    const snapshot = readPointerSnapshot(event);
    const { element, bounds, point } = snapshot;

    element.setPointerCapture(event.pointerId);
    event.preventDefault();
    const nextSession = {
      pointerId: event.pointerId,
      pageIndex,
      bounds,
      origin: point,
      current: point,
    };
    sessionRef.current = nextSession;
    setSession(nextSession);
  }

  function updateDrag(event: ReactPointerEvent<HTMLElement>): void {
    const snapshot = readPointerSnapshot(event);
    const currentSession = sessionRef.current;
    if (!currentSession || currentSession.pointerId !== snapshot.pointerId) {
      return;
    }

    const nextSession = {
      ...currentSession,
      bounds: snapshot.bounds,
      current: snapshot.point,
    };
    sessionRef.current = nextSession;
    setSession(nextSession);
  }

  function endDrag(event: ReactPointerEvent<HTMLElement>): void {
    const snapshot = readPointerSnapshot(event);
    const currentSession = sessionRef.current;
    if (!currentSession || currentSession.pointerId !== snapshot.pointerId) {
      return;
    }

    const bounds = snapshot.bounds;
    const rect = clampRectToBounds(
      rectFromPoints(currentSession.origin, snapshot.point),
      bounds,
    );

    if (snapshot.element.hasPointerCapture(snapshot.pointerId)) {
      snapshot.element.releasePointerCapture(snapshot.pointerId);
    }

    sessionRef.current = null;
    setSession(null);

    event.preventDefault();
    if (isRectLargeEnough(rect, minimumSize)) {
      onSelectionCommit({
        pageIndex: currentSession.pageIndex,
        rect,
        bounds,
      });
    }
  }

  function cancelDrag(): void {
    sessionRef.current = null;
    setSession(null);
  }

  return {
    activePageIndex: session?.pageIndex ?? null,
    previewRect: session
      ? clampRectToBounds(rectFromPoints(session.origin, session.current), session.bounds)
      : null,
    isDragging: session !== null,
    beginDrag,
    updateDrag,
    endDrag,
    cancelDrag,
  };
}

interface PointerSnapshot {
  element: HTMLElement;
  pointerId: number;
  bounds: SelectionSize;
  point: SelectionPoint;
}

function readPointerSnapshot(event: ReactPointerEvent<HTMLElement>): PointerSnapshot {
  const element = event.currentTarget;
  const bounds = {
    width: element.clientWidth,
    height: element.clientHeight,
  };

  return {
    element,
    pointerId: event.pointerId,
    bounds,
    point: pointFromEvent(event, element, bounds),
  };
}

function pointFromEvent(
  event: ReactPointerEvent<HTMLElement>,
  element: HTMLElement,
  bounds: SelectionSize,
): SelectionPoint {
  const rect = element.getBoundingClientRect();

  return clampPointToBounds(
    {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    },
    bounds,
  );
}
