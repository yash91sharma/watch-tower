// Test helper: render the app routes at a path, with a new query client.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";

import { authStateQuery } from "@/api/auth";
import { onUnauthorized } from "@/api/client";
import { routes } from "@/routes";

// Same 401 handler as in App.tsx.
export function renderRoute(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  onUnauthorized(() => {
    void queryClient.resetQueries({ queryKey: authStateQuery.queryKey });
    void router.navigate("/login");
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { ...result, router, queryClient };
}
