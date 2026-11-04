// Queries for the API data. useEventStream refetches them by key.
import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";

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
