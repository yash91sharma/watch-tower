// Auth guard: shows its page only in the matching auth state. Else it opens the page for the state.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate } from "react-router";

import { authStateQuery } from "@/api/queries";

type Area = "setup" | "login" | "app";

const areaPath: Record<Area, string> = { setup: "/setup", login: "/login", app: "/" };

export function AuthGuard({ area, children }: { area: Area; children: ReactNode }) {
  const { data, error } = useQuery(authStateQuery);
  if (!data) {
    // The router error boundary shows the error page. A failed refetch keeps the old
    // state (for example while WT restarts): the connection banner shows it.
    if (error) throw error;
    return <p className="px-4 py-8 text-center text-muted-foreground">Loading…</p>;
  }

  const target: Area = data.setup_required ? "setup" : data.logged_in ? "app" : "login";
  if (target !== area) return <Navigate to={areaPath[target]} replace />;
  return children;
}
