// Vitest setup: DOM matchers, MSW server, fake EventSource, a small screen (matchMedia), and cleanup (DOM, handlers, localStorage) after each test.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, vi } from "vitest";

import { FakeEventSource } from "@/test/eventSource";
import { setDesktop } from "@/test/media";
import { server } from "@/test/server";

// A request with no handler fails the test.
beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
});
beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
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
