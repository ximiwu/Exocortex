import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ContextMenu } from "./ContextMenu";

describe("ContextMenu", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps the menu inside the viewport when the anchor is near the bottom-right corner", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => ({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 180,
      bottom: 220,
      width: 180,
      height: 220,
      toJSON: () => ({}),
    }));

    render(
      <ContextMenu anchor={{ x: 980, y: 760 }} open onClose={vi.fn()}>
        <button type="button" role="menuitem">
          delete
        </button>
      </ContextMenu>,
    );

    const menu = screen.getByRole("menu");
    await waitFor(() => {
      expect(menu).toHaveStyle({
        left: "832px",
        top: "536px",
        visibility: "visible",
      });
    });
  });
});
