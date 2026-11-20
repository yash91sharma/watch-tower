// Vitest setup: DOM matchers, MSW server, fake EventSource, fake uPlot and ResizeObserver,
// a small screen (matchMedia), and cleanup (DOM, handlers, localStorage) after each test.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, vi } from "vitest";

import { FakeEventSource } from "@/test/eventSource";
import { setDesktop } from "@/test/media";
import { server } from "@/test/server";
import { FakeResizeObserver, plots, resizeCallbacks } from "@/test/uplot";

vi.mock("uplot", () => import("@/test/uplot"));

// A request with no handler fails the test.
beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
});
beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  plots.length = 0;
  resizeCallbacks.length = 0;
  setDesktop(false);
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => {
  server.close();
});
