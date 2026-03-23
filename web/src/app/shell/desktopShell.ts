import { useEffect, useState } from "react";

export interface DesktopShellSnapshot {
  isDesktopShell: boolean;
  isMaximized: boolean;
}

interface DesktopShellWindowState {
  isMaximized?: boolean;
}

interface PywebviewStateChangeDetail {
  key?: string;
  value?: unknown;
}

interface PywebviewStateChangeEvent extends Event {
  detail?: PywebviewStateChangeDetail;
}

interface PywebviewState extends EventTarget {
  isMaximized?: boolean;
}

interface PywebviewApi {
  minimize?: () => Promise<unknown> | unknown;
  toggleMaximize?: () => Promise<unknown> | unknown;
  close?: () => Promise<unknown> | unknown;
  getWindowState?: () => Promise<DesktopShellWindowState> | DesktopShellWindowState;
}

interface PywebviewBridge {
  api?: PywebviewApi;
  state?: PywebviewState;
}

declare global {
  interface Window {
    pywebview?: PywebviewBridge;
  }
}

const FALLBACK_SNAPSHOT: DesktopShellSnapshot = {
  isDesktopShell: false,
  isMaximized: false,
};

export interface DesktopShellBridge {
  getSnapshot(): DesktopShellSnapshot;
  resolveSnapshot(): Promise<DesktopShellSnapshot>;
  subscribe(listener: (snapshot: DesktopShellSnapshot) => void): () => void;
  minimize(): Promise<void>;
  toggleMaximize(): Promise<void>;
  close(): Promise<void>;
}

export function readDesktopShellSnapshot(
  target: Window | null | undefined,
): DesktopShellSnapshot {
  if (!target?.pywebview) {
    return FALLBACK_SNAPSHOT;
  }

  return {
    isDesktopShell: true,
    isMaximized: Boolean(target.pywebview.state?.isMaximized),
  };
}

export function createDesktopShellBridge(
  target: Window | null | undefined = typeof window === "undefined" ? undefined : window,
): DesktopShellBridge {
  async function invoke(command: keyof PywebviewApi): Promise<void> {
    const handler = target?.pywebview?.api?.[command];
    if (!handler) {
      return;
    }

    await Promise.resolve(handler.call(target.pywebview?.api));
  }

  async function resolveSnapshot(): Promise<DesktopShellSnapshot> {
    const baseSnapshot = readDesktopShellSnapshot(target);
    const getWindowState = target?.pywebview?.api?.getWindowState;
    if (!baseSnapshot.isDesktopShell || !getWindowState) {
      return baseSnapshot;
    }

    try {
      const response = await Promise.resolve(getWindowState.call(target.pywebview?.api));
      return {
        ...baseSnapshot,
        isMaximized:
          typeof response?.isMaximized === "boolean"
            ? response.isMaximized
            : baseSnapshot.isMaximized,
      };
    } catch {
      return baseSnapshot;
    }
  }

  function subscribe(listener: (snapshot: DesktopShellSnapshot) => void): () => void {
    if (!target) {
      return () => {};
    }

    let detachStateListener = () => {};

    const publishSnapshot = () => {
      listener(readDesktopShellSnapshot(target));
    };

    const attachStateListener = () => {
      detachStateListener();

      const stateTarget = target.pywebview?.state;
      if (!stateTarget) {
        return;
      }

      const handleStateChange = (event: Event) => {
        const detail = (event as PywebviewStateChangeEvent).detail;
        if (!detail || detail.key === "isMaximized") {
          publishSnapshot();
        }
      };

      stateTarget.addEventListener("change", handleStateChange as EventListener);
      detachStateListener = () => {
        stateTarget.removeEventListener("change", handleStateChange as EventListener);
      };
    };

    const handleReady = () => {
      attachStateListener();
      void resolveSnapshot().then(listener);
    };

    attachStateListener();
    target.addEventListener("pywebviewready", handleReady as EventListener);
    publishSnapshot();

    return () => {
      target.removeEventListener("pywebviewready", handleReady as EventListener);
      detachStateListener();
    };
  }

  return {
    getSnapshot: () => readDesktopShellSnapshot(target),
    resolveSnapshot,
    subscribe,
    minimize: () => invoke("minimize"),
    toggleMaximize: () => invoke("toggleMaximize"),
    close: () => invoke("close"),
  };
}

export function useDesktopShell() {
  const [bridge] = useState(() => createDesktopShellBridge());
  const [snapshot, setSnapshot] = useState<DesktopShellSnapshot>(() => bridge.getSnapshot());

  useEffect(() => {
    const unsubscribe = bridge.subscribe(setSnapshot);
    void bridge.resolveSnapshot().then(setSnapshot);
    return unsubscribe;
  }, [bridge]);

  return {
    ...snapshot,
    minimize: async () => {
      await bridge.minimize();
      setSnapshot(await bridge.resolveSnapshot());
    },
    toggleMaximize: async () => {
      await bridge.toggleMaximize();
      setSnapshot(await bridge.resolveSnapshot());
    },
    close: async () => {
      await bridge.close();
    },
  };
}
