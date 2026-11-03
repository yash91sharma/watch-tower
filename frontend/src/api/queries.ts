// Queries for the API data. useEventStream refetches them by key.
import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";

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
