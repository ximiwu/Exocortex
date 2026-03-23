import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createExocortexApi } from "./client";

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new Event("close"));
  }

  emitOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  emitClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new Event("close"));
  }

  emitMessage(payload: unknown) {
    this.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify(payload),
      }),
    );
  }
}

describe("task event websocket subscription", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("reconnects with replay and preserves assetName normalization after a disconnect", async () => {
    const listener = vi.fn();
    const client = createExocortexApi({
      apiBase: "http://localhost:9000/api",
      mode: "live",
    });

    const unsubscribe = client.subscribeToTaskEvents(listener);

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0]?.url).toBe("ws://localhost:9000/api/ws/tasks");

    MockWebSocket.instances[0]?.emitOpen();
    MockWebSocket.instances[0]?.emitClose();

    await vi.advanceTimersByTimeAsync(250);

    expect(MockWebSocket.instances).toHaveLength(2);
    expect(MockWebSocket.instances[1]?.url).toBe("ws://localhost:9000/api/ws/tasks?replay=true");

    MockWebSocket.instances[1]?.emitOpen();
    MockWebSocket.instances[1]?.emitMessage({
      taskId: "task-1",
      kind: "group_dive",
      assetName: "asset-a",
      status: "completed",
      eventType: "completed",
      message: "done",
      progress: 1,
      artifactPath: "group_data/1/img_explainer_data/enhanced.md",
      payload: null,
      timestamp: "2026-03-22T12:00:00Z",
    });

    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({
        taskId: "task-1",
        kind: "group_dive",
        assetName: "asset-a",
        status: "completed",
      }),
    );

    unsubscribe();
    const connectionCount = MockWebSocket.instances.length;
    MockWebSocket.instances[1]?.emitClose();

    await vi.advanceTimersByTimeAsync(1000);

    expect(MockWebSocket.instances).toHaveLength(connectionCount);
  });
});
