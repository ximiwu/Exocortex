import { describe, expect, it } from "vitest";

import type { AssetState } from "../../app/types";
import { resolveLocatePageIndex } from "./treeUtils";

describe("sidebar tree utils", () => {
  it("uses the first blockIds entry when resolving locate-in-pdf page", () => {
    const assetState: AssetState = {
      asset: {
        name: "demo",
        pageCount: 12,
        pdfPath: "demo/raw.pdf",
      },
      references: [],
      blocks: [
        {
          blockId: 2,
          pageIndex: 8,
          fractionRect: { x: 0, y: 0, width: 0.1, height: 0.1 },
          groupIdx: 5,
        },
        {
          blockId: 9,
          pageIndex: 3,
          fractionRect: { x: 0, y: 0, width: 0.1, height: 0.1 },
          groupIdx: 5,
        },
      ],
      mergeOrder: [],
      nextBlockId: 10,
      groups: [
        {
          groupIdx: 5,
          blockIds: [9, 2],
        },
      ],
      uiState: {
        currentPage: 1,
        zoom: 1,
        pdfScrollFraction: 0,
        pdfScrollLeftFraction: 0,
        currentMarkdownPath: null,
        openMarkdownPaths: [],
        sidebarCollapsed: false,
        sidebarCollapsedNodeIds: [],
        markdownScrollFractions: {},
      },
    };

    expect(resolveLocatePageIndex(assetState, 5)).toBe(3);
  });
});
