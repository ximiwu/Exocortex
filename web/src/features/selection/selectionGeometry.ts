export interface SelectionPoint {
  x: number;
  y: number;
}

export interface SelectionSize {
  width: number;
  height: number;
}

export interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function clampSelectionValue(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function clampPointToBounds(point: SelectionPoint, bounds: SelectionSize): SelectionPoint {
  return {
    x: clampSelectionValue(point.x, 0, bounds.width),
    y: clampSelectionValue(point.y, 0, bounds.height),
  };
}

export function rectFromPoints(start: SelectionPoint, end: SelectionPoint): SelectionRect {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  const width = Math.abs(end.x - start.x);
  const height = Math.abs(end.y - start.y);

  return { x, y, width, height };
}

export function clampRectToBounds(
  rect: SelectionRect,
  bounds: SelectionSize,
): SelectionRect {
  const x = clampSelectionValue(rect.x, 0, bounds.width);
  const y = clampSelectionValue(rect.y, 0, bounds.height);
  const maxWidth = Math.max(0, bounds.width - x);
  const maxHeight = Math.max(0, bounds.height - y);

  return {
    x,
    y,
    width: clampSelectionValue(rect.width, 0, maxWidth),
    height: clampSelectionValue(rect.height, 0, maxHeight),
  };
}

export function isRectLargeEnough(rect: SelectionRect, minimumSize = 4): boolean {
  return rect.width >= minimumSize && rect.height >= minimumSize;
}
