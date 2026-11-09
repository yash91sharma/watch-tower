import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useEventStream } from "@/api/useEventStream";
import { FakeEventSource } from "@/test/eventSource";

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

/** The hook with 3 queries (the app keys) that count their fetches. */
async function renderStream() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const fetches = { containers: 0, checks: 0, settings: 0 };
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const hook = renderHook(
    () => {
      useQuery({ queryKey: ["containers"], queryFn: () => ++fetches.containers });
      useQuery({ queryKey: ["checks", "status"], queryFn: () => ++fetches.checks });
      useQuery({ queryKey: ["settings"], queryFn: () => ++fetches.settings });
      return useEventStream();
    },
    { wrapper },
  );
  await waitFor(() => {
    expect(fetches).toEqual({ containers: 1, checks: 1, settings: 1 });
  });
  return { ...hook, fetches };
}

test("the hook opens /api/stream", async () => {
  await renderStream();

  expect(FakeEventSource.last.url).toBe("/api/stream");
});

test("a container event refetches the containers", async () => {
  const { fetches } = await renderStream();

  act(() => {
    FakeEventSource.last.emit("container", { name: "web" });
  });

  await waitFor(() => {
    expect(fetches).toEqual({ containers: 2, checks: 1, settings: 1 });
  });
});

test("a check event refetches the check status and the containers", async () => {
  const { fetches } = await renderStream();

  act(() => {
    FakeEventSource.last.emit("check", { running: false });
  });

  await waitFor(() => {
    expect(fetches).toEqual({ containers: 2, checks: 2, settings: 1 });
  });
});

test("a docker event gives the Docker state and refetches the containers", async () => {
  const { result, fetches } = await renderStream();
  expect(result.current.docker).toBe(true);

  act(() => {
    FakeEventSource.last.emit("docker", { connected: false });
  });
  expect(result.current.docker).toBe(false);

  act(() => {
    FakeEventSource.last.emit("docker", { connected: true });
  });
  expect(result.current.docker).toBe(true);
  // Only the reconnect of Docker refetches.
  await waitFor(() => {
    expect(fetches).toEqual({ containers: 2, checks: 1, settings: 1 });
  });
});

test("the first open refetches nothing", async () => {
  const { fetches } = await renderStream();

  act(() => {
    FakeEventSource.last.emit("open");
  });

  await vi.advanceTimersByTimeAsync(100);
  expect(fetches).toEqual({ containers: 1, checks: 1, settings: 1 });
});

test("after an error, the hook connects again and refetches all queries", async () => {
  const { result, fetches } = await renderStream();
  const first = FakeEventSource.last;

  act(() => {
    first.emit("open");
    first.emit("error");
  });
  expect(result.current.wt).toBe(false);
  expect(first.closed).toBe(true);

  await act(() => vi.advanceTimersByTimeAsync(3000));
  expect(FakeEventSource.instances).toHaveLength(2);
  act(() => {
    FakeEventSource.last.emit("open");
  });

  expect(result.current.wt).toBe(true);
  await waitFor(() => {
    expect(fetches).toEqual({ containers: 2, checks: 2, settings: 2 });
  });
});

test("unmount closes the stream", async () => {
  const { unmount } = await renderStream();

  unmount();

  expect(FakeEventSource.last.closed).toBe(true);
});

test("an error refetches the auth state at once", async () => {
  // EventSource does not give the HTTP status. When the session is gone (401), the new auth
  // state makes the auth guard open /login, and the stream stops with the unmount.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let authFetches = 0;
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  renderHook(
    () => {
      useQuery({ queryKey: ["auth", "state"], queryFn: () => ++authFetches });
      return useEventStream();
    },
    { wrapper },
  );
  await waitFor(() => {
    expect(authFetches).toBe(1);
  });

  act(() => {
    FakeEventSource.last.emit("error");
  });

  await waitFor(() => {
    expect(authFetches).toBe(2);
  });
});
