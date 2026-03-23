import { describe, expect, it } from "vitest";

import {
  DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
  DEFAULT_SIDEBAR_WIDTH_RATIO,
  SHELL_COLLAPSED_SIDEBAR_WIDTH_PX,
  SHELL_MARKDOWN_MIN_WIDTH_PX,
  SHELL_RIGHT_RAIL_MIN_WIDTH_PX,
  SHELL_SIDEBAR_MIN_WIDTH_PX,
  clampRightRailWidthPx,
  clampSidebarWidthPx,
  resolveDesktopPaneLayout,
  widthToRatio,
} from "./paneLayout";

describe("pane layout", () => {
  it("restores the baseline desktop ratios", () => {
    const layout = resolveDesktopPaneLayout({
      containerWidthPx: 980,
      sidebarCollapsed: false,
      sidebarWidthRatio: DEFAULT_SIDEBAR_WIDTH_RATIO,
      rightRailWidthRatio: DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
    });

    expect(layout.sidebarWidthPx).toBe(SHELL_SIDEBAR_MIN_WIDTH_PX);
    expect(layout.markdownWidthPx).toBe(SHELL_MARKDOWN_MIN_WIDTH_PX);
    expect(layout.rightRailWidthPx).toBe(SHELL_RIGHT_RAIL_MIN_WIDTH_PX);
  });

  it("clamps splitter widths so desktop minimums are preserved", () => {
    expect(clampSidebarWidthPx(40, 960, SHELL_RIGHT_RAIL_MIN_WIDTH_PX)).toBe(
      SHELL_SIDEBAR_MIN_WIDTH_PX,
    );
    expect(clampRightRailWidthPx(40, 960, SHELL_SIDEBAR_MIN_WIDTH_PX)).toBe(
      SHELL_RIGHT_RAIL_MIN_WIDTH_PX,
    );
  });

  it("keeps the collapsed sidebar width fixed while restoring the right rail ratio", () => {
    const layout = resolveDesktopPaneLayout({
      containerWidthPx: 980,
      sidebarCollapsed: true,
      sidebarWidthRatio: DEFAULT_SIDEBAR_WIDTH_RATIO,
      rightRailWidthRatio: DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
    });

    expect(layout.sidebarWidthPx).toBe(SHELL_COLLAPSED_SIDEBAR_WIDTH_PX);
    expect(layout.markdownWidthPx).toBeGreaterThanOrEqual(SHELL_MARKDOWN_MIN_WIDTH_PX);
    expect(widthToRatio(layout.rightRailWidthPx, layout.panelWidthPx)).toBeCloseTo(
      DEFAULT_RIGHT_RAIL_WIDTH_RATIO,
      2,
    );
  });
});
