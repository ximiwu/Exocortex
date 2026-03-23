export const DESKTOP_WORKSPACE_BREAKPOINT_PX = 1280;
export const SHELL_SPLITTER_WIDTH_PX = 10;
export const SHELL_COLLAPSED_SIDEBAR_WIDTH_PX = 46;
export const SHELL_SIDEBAR_MIN_WIDTH_PX = 180;
export const SHELL_MARKDOWN_MIN_WIDTH_PX = 440;
export const SHELL_RIGHT_RAIL_MIN_WIDTH_PX = 340;
export const DEFAULT_SIDEBAR_WIDTH_RATIO =
  SHELL_SIDEBAR_MIN_WIDTH_PX /
  (SHELL_SIDEBAR_MIN_WIDTH_PX + SHELL_MARKDOWN_MIN_WIDTH_PX + SHELL_RIGHT_RAIL_MIN_WIDTH_PX);
export const DEFAULT_RIGHT_RAIL_WIDTH_RATIO =
  SHELL_RIGHT_RAIL_MIN_WIDTH_PX /
  (SHELL_SIDEBAR_MIN_WIDTH_PX + SHELL_MARKDOWN_MIN_WIDTH_PX + SHELL_RIGHT_RAIL_MIN_WIDTH_PX);

export interface DesktopPaneLayout {
  panelWidthPx: number;
  sidebarWidthPx: number;
  markdownWidthPx: number;
  rightRailWidthPx: number;
  visibleSplitterCount: number;
}

interface ResolveDesktopPaneLayoutInput {
  containerWidthPx: number;
  sidebarCollapsed: boolean;
  sidebarWidthRatio: number | null | undefined;
  rightRailWidthRatio: number | null | undefined;
}

export function normalizePaneRatio(
  rawRatio: number | null | undefined,
  fallbackRatio: number,
): number {
  if (typeof rawRatio !== "number" || !Number.isFinite(rawRatio) || rawRatio <= 0) {
    return fallbackRatio;
  }

  return Math.min(0.8, Math.max(0.05, rawRatio));
}

export function resolveDesktopPaneLayout({
  containerWidthPx,
  sidebarCollapsed,
  sidebarWidthRatio,
  rightRailWidthRatio,
}: ResolveDesktopPaneLayoutInput): DesktopPaneLayout {
  const visibleSplitterCount = sidebarCollapsed ? 1 : 2;
  const panelWidthPx = Math.max(0, containerWidthPx - visibleSplitterCount * SHELL_SPLITTER_WIDTH_PX);
  const safeSidebarRatio = normalizePaneRatio(sidebarWidthRatio, DEFAULT_SIDEBAR_WIDTH_RATIO);
  const safeRightRailRatio = normalizePaneRatio(rightRailWidthRatio, DEFAULT_RIGHT_RAIL_WIDTH_RATIO);

  if (sidebarCollapsed) {
    const sidebarWidthPx = SHELL_COLLAPSED_SIDEBAR_WIDTH_PX;
    const rightRailWidthPx = clampRightRailWidthPx(
      Math.round(panelWidthPx * safeRightRailRatio),
      panelWidthPx,
      sidebarWidthPx,
    );
    const markdownWidthPx = Math.max(0, panelWidthPx - sidebarWidthPx - rightRailWidthPx);

    return {
      panelWidthPx,
      sidebarWidthPx,
      markdownWidthPx,
      rightRailWidthPx,
      visibleSplitterCount,
    };
  }

  const sidebarWidthPx = clampSidebarWidthPx(
    Math.round(panelWidthPx * safeSidebarRatio),
    panelWidthPx,
    Math.max(SHELL_RIGHT_RAIL_MIN_WIDTH_PX, Math.round(panelWidthPx * safeRightRailRatio)),
  );
  const rightRailWidthPx = clampRightRailWidthPx(
    Math.round(panelWidthPx * safeRightRailRatio),
    panelWidthPx,
    sidebarWidthPx,
  );
  const markdownWidthPx = Math.max(0, panelWidthPx - sidebarWidthPx - rightRailWidthPx);

  return {
    panelWidthPx,
    sidebarWidthPx,
    markdownWidthPx,
    rightRailWidthPx,
    visibleSplitterCount,
  };
}

export function clampSidebarWidthPx(
  sidebarWidthPx: number,
  panelWidthPx: number,
  rightRailWidthPx: number,
): number {
  const maxSidebarWidthPx = Math.max(
    SHELL_SIDEBAR_MIN_WIDTH_PX,
    panelWidthPx - SHELL_MARKDOWN_MIN_WIDTH_PX - rightRailWidthPx,
  );

  return Math.min(maxSidebarWidthPx, Math.max(SHELL_SIDEBAR_MIN_WIDTH_PX, Math.round(sidebarWidthPx)));
}

export function clampRightRailWidthPx(
  rightRailWidthPx: number,
  panelWidthPx: number,
  sidebarWidthPx: number,
): number {
  const maxRightRailWidthPx = Math.max(
    SHELL_RIGHT_RAIL_MIN_WIDTH_PX,
    panelWidthPx - sidebarWidthPx - SHELL_MARKDOWN_MIN_WIDTH_PX,
  );

  return Math.min(
    maxRightRailWidthPx,
    Math.max(SHELL_RIGHT_RAIL_MIN_WIDTH_PX, Math.round(rightRailWidthPx)),
  );
}

export function widthToRatio(widthPx: number, panelWidthPx: number): number {
  if (!panelWidthPx || panelWidthPx <= 0) {
    return 0;
  }

  return widthPx / panelWidthPx;
}
