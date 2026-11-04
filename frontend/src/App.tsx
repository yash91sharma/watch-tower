// App root: data cache and routes.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router";

import { authStateQuery } from "@/api/queries";
import { onUnauthorized } from "@/api/client";
import { routes } from "@/routes";

const queryClient = new QueryClient();
const router = createBrowserRouter(routes);
// Reset the old auth state, so that the auth guard gets the new state.
onUnauthorized(() => {
  void queryClient.resetQueries({ queryKey: authStateQuery.queryKey });
  void router.navigate("/login");
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
