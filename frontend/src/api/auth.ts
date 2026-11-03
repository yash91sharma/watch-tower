// Auth state query. The auth guard reads it. A 401 resets it.
import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";

export const authStateQuery = queryOptions({
  queryKey: ["auth", "state"],
  queryFn: async () => unwrap(await api.GET("/api/auth/state")),
});
