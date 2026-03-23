import { describe, expect, it } from "vitest";

import { createDesktopShellBridge, readDesktopShellSnapshot } from "./desktopShell";

describe("desktop shell bridge", () => {
  it("is a safe no-op outside pywebview", async () => {
    const fakeWindow = new EventTarget() as Window;
    const bridge = createDesktopShellBridge(fakeWindow);

    expect(readDesktopShellSnapshot(fakeWindow)).toEqual({
      isDesktopShell: false,
      isMaximized: false,
    });
    await expect(bridge.resolveSnapshot()).resolves.toEqual({
      isDesktopShell: false,
      isMaximized: false,
    });
    await expect(bridge.minimize()).resolves.toBeUndefined();
    await expect(bridge.toggleMaximize()).resolves.toBeUndefined();
    await expect(bridge.close()).resolves.toBeUndefined();
  });
});
