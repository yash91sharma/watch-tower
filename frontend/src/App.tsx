// App root: data cache and routes. Task 13.1 adds the app shell and all routes.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router";

const queryClient = new QueryClient();

const router = createBrowserRouter([
  { path: "/", element: <h1 className="p-4 text-xl font-semibold">Watch Tower</h1> },
]);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
