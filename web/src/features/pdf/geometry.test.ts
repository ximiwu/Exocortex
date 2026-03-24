import { describe, expect, it } from "vitest";

import {
  collectContainedTextBoxesForPage,
  findPreheatPageIndexes,
  isRectFullyContained,
} from "./geometry";
import type { PdfBlockRecord, PdfTextBox } from "./types";

describe("findPreheatPageIndexes", () => {
  it("biases forward preheat toward the downward scroll direction", () => {
    expect(
      findPreheatPageIndexes(12, [1, 2, 3, 4, 5, 6, 7, 8, 9], {
        currentPageIndex: 5,
        direction: 1,
        aheadCount: 3,
        behindCount: 1,
      }),
    ).toEqual([10, 11, 0]);
  });

  it("biases backward preheat toward the upward scroll direction", () => {
    expect(
      findPreheatPageIndexes(12, [2, 3, 4, 5, 6, 7, 8], {
        currentPageIndex: 5,
        direction: -1,
        aheadCount: 3,
        behindCount: 1,
      }),
    ).toEqual([1, 0, 9, 10]);
  });
});

describe("text box containment", () => {
  const block: PdfBlockRecord = {
    blockId: 1,
    pageIndex: 0,
    fractionRect: {
      x: 0.1,
      y: 0.2,
      width: 0.5,
      height: 0.4,
    },
    groupIdx: null,
  };

  it("matches when the text box is fully contained", () => {
    expect(
      isRectFullyContained(block.fractionRect!, {
        x: 0.15,
        y: 0.25,
        width: 0.1,
        height: 0.05,
      }),
    ).toBe(true);
  });

  it("treats edge-touching as contained", () => {
    expect(
      isRectFullyContained(block.fractionRect!, {
        x: 0.1,
        y: 0.2,
        width: 0.5,
        height: 0.4,
      }),
    ).toBe(true);
  });

  it("does not match partial coverage", () => {
    expect(
      isRectFullyContained(block.fractionRect!, {
        x: 0.59,
        y: 0.25,
        width: 0.1,
        height: 0.05,
      }),
    ).toBe(false);
  });

  it("ignores text boxes from other pages", () => {
    const textBoxes: PdfTextBox[] = [
      {
        itemIndex: 1,
        pageIndex: 0,
        fractionRect: { x: 0.12, y: 0.25, width: 0.1, height: 0.05 },
      },
      {
        itemIndex: 2,
        pageIndex: 1,
        fractionRect: { x: 0.12, y: 0.25, width: 0.1, height: 0.05 },
      },
    ];

    expect(collectContainedTextBoxesForPage(0, [block], textBoxes)).toHaveLength(1);
  });

  it("dedupes matches across overlapping blocks", () => {
    const overlappingBlock: PdfBlockRecord = {
      blockId: 2,
      pageIndex: 0,
      fractionRect: { x: 0.08, y: 0.18, width: 0.52, height: 0.44 },
      groupIdx: null,
    };
    const textBoxes: PdfTextBox[] = [
      {
        itemIndex: 1,
        pageIndex: 0,
        fractionRect: { x: 0.15, y: 0.25, width: 0.1, height: 0.05 },
      },
    ];

    const result = collectContainedTextBoxesForPage(0, [block, overlappingBlock], textBoxes);
    expect(result).toHaveLength(1);
    expect(result[0]?.pageIndex).toBe(0);
  });

  it("skips text box overlays for blocks that already belong to a group", () => {
    const groupedBlock: PdfBlockRecord = {
      ...block,
      groupIdx: 7,
    };
    const textBoxes: PdfTextBox[] = [
      {
        itemIndex: 1,
        pageIndex: 0,
        fractionRect: { x: 0.15, y: 0.25, width: 0.1, height: 0.05 },
      },
    ];

    expect(collectContainedTextBoxesForPage(0, [groupedBlock], textBoxes)).toEqual([]);
  });
});
