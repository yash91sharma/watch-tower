// Queries for the API data. useEventStream refetches them by key.
import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { RangeKey } from "@/api/types";

// The auth guard reads the auth state. A 401 resets it.
export const authStateQuery = queryOptions({
  queryKey: ["auth", "state"],
  queryFn: async () => unwrap(await api.GET("/api/auth/state")),
});

export const containersQuery = queryOptions({
  queryKey: ["containers"],
  queryFn: async () => unwrap(await api.GET("/api/containers")),
});

export const checkStatusQuery = queryOptions({
  queryKey: ["checks", "status"],
  queryFn: async () => unwrap(await api.GET("/api/checks/status")),
});

export function containerQuery(name: string) {
  return queryOptions({
    queryKey: ["containers", name],
    queryFn: async () => unwrap(await api.GET("/api/containers/{name}", { params: { path: { name } } })),
  });
}

export const settingsQuery = queryOptions({
  queryKey: ["settings"],
  queryFn: async () => unwrap(await api.GET("/api/settings")),
});

// Metrics. The `metrics` event with kind "current" refetches the overview, with kind
// "history" the sparklines and all history queries (prefix ["metrics", "history"]).
export const overviewQuery = queryOptions({
  queryKey: ["metrics", "overview"],
  queryFn: async () => unwrap(await api.GET("/api/metrics/overview")),
});

export const sparklinesQuery = queryOptions({
  queryKey: ["metrics", "sparklines"],
  queryFn: async () => unwrap(await api.GET("/api/metrics/sparklines")),
});

export const historyKey = ["metrics", "history"] as const;

export function vmHistoryQuery(range: RangeKey) {
  return queryOptions({
    queryKey: [...historyKey, "vm", range],
    queryFn: async () => unwrap(await api.GET("/api/metrics/vm/history", { params: { query: { range } } })),
  });
}

export function containerHistoryQuery(name: string, range: RangeKey) {
  return queryOptions({
    queryKey: [...historyKey, "containers", name, range],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/metrics/containers/{name}/history", { params: { path: { name }, query: { range } } }),
      ),
  });
}
