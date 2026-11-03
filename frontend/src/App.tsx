// App root: data cache and routes.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router";

import { onUnauthorized } from "@/api/client";
import { routes } from "@/routes";

const queryClient = new QueryClient();
const router = createBrowserRouter(routes);
onUnauthorized(() => void router.navigate("/login"));

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
