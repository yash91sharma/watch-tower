import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useLogStream } from "@/api/useLogStream";
import { FakeEventSource } from "@/test/eventSource";

let frames: FrameRequestCallback[] = [];

// Run the animation frame callbacks only when the test says so.
beforeEach(() => {
  frames = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => frames.push(callback));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function runFrames() {
  act(() => {
    const now = frames;
    frames = [];
    for (const callback of now) callback(0);
  });
}

function send(text: string, stream = "stdout") {
  act(() => {
    FakeEventSource.last.emit("message", { time: "2026-11-02T06:00:00Z", stream, text });
  });
}

const texts = (lines: { text: string }[]) => lines.map((item) => item.text);

test("the hook opens the logs SSE with the tail size", () => {
  renderHook(() => useLogStream("my app", 500));

  expect(FakeEventSource.last.url).toBe("/api/containers/my%20app/logs?tail=500");
});

test("new lines are added once per animation frame", () => {
  const { result } = renderHook(() => useLogStream("web", 500));

  send("a");
  send("b");
  send("c", "stderr");
  expect(result.current.lines).toEqual([]);
  expect(frames).toHaveLength(1);

  runFrames();
  expect(texts(result.current.lines)).toEqual(["a", "b", "c"]);
  expect(result.current.lines[2]?.stream).toBe("stderr");
});

test("a reconnect clears the buffer, so the tail gives no duplicate lines", () => {
  const { result } = renderHook(() => useLogStream("web", 500));
  act(() => {
    FakeEventSource.last.emit("open");
  });
  send("a");
  send("b");
  runFrames();

  // The browser connects again. WT sends the tail again.
  act(() => {
    FakeEventSource.last.emit("open");
  });
  send("a");
  send("b");
  send("c");
  runFrames();

  expect(texts(result.current.lines)).toEqual(["a", "b", "c"]);
});

test("open also drops lines that wait for a frame", () => {
  const { result } = renderHook(() => useLogStream("web", 500));
  send("old");

  act(() => {
    FakeEventSource.last.emit("open");
  });
  send("new");
  runFrames();

  expect(texts(result.current.lines)).toEqual(["new"]);
});

test("an error event from WT gives the error text", () => {
  const { result } = renderHook(() => useLogStream("web", 500));

  act(() => {
    FakeEventSource.last.emit("error", "Docker is not connected");
  });

  expect(result.current.error).toBe("Docker is not connected");
});

test("a new tail size opens a new stream and closes the old one", () => {
  const { rerender } = renderHook(({ tail }) => useLogStream("web", tail), { initialProps: { tail: 500 } });
  const first = FakeEventSource.last;

  rerender({ tail: 1000 });

  expect(first.closed).toBe(true);
  expect(FakeEventSource.last.url).toBe("/api/containers/web/logs?tail=1000");
});
