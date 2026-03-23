import { describe, expect, it } from "vitest";

import {
  deriveGroupContext,
  deriveTutorContext,
  findPreferredGroupMarkdownNode,
  isTutorHistoryMarkdown,
} from "./schema";

describe("workflow schema helpers", () => {
  it("derives group and tutor context from markdown paths", () => {
    expect(deriveGroupContext("group_data/12/img_explainer_data/enhanced.md")).toEqual({
      groupIdx: 12,
    });
    expect(deriveGroupContext("references/background.md")).toBeNull();
    expect(deriveTutorContext("group_data/7/tutor_data/3/focus.md")).toEqual({
      groupIdx: 7,
      tutorIdx: 3,
    });
    expect(deriveTutorContext("group_data/7/content.md")).toBeNull();
  });

  it("detects tutor history markdown path", () => {
    expect(isTutorHistoryMarkdown("group_data/1/tutor_data/1/ask_history/2.md")).toBe(true);
    expect(isTutorHistoryMarkdown("group_data/1/tutor_data/1/answer.md")).toBe(false);
    expect(isTutorHistoryMarkdown(null)).toBe(false);
  });

  it("prefers enhanced group markdown over fallback candidates", () => {
    const tree = [
      {
        id: "group:1",
        kind: "group",
        title: "group 1",
        path: "group_data/1/content.md",
        children: [
          {
            id: "group:1:enhanced",
            kind: "markdown",
            title: "enhanced",
            path: "group_data/1/img_explainer_data/enhanced.md",
            children: [],
          },
        ],
      },
      {
        id: "group:2",
        kind: "group",
        title: "group 2",
        path: "group_data/2/content.md",
        children: [],
      },
    ];

    const preferred = findPreferredGroupMarkdownNode(tree as never, 1);
    expect(preferred?.path).toBe("group_data/1/img_explainer_data/enhanced.md");
    expect(findPreferredGroupMarkdownNode(tree as never, 99)).toBeNull();
  });
});
