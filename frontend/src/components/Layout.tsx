// Page frame for the logged-in app: top nav and the page below it.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, useNavigate } from "react-router";

import { authStateQuery } from "@/api/auth";
import { api, unwrap } from "@/api/client";
import { Button } from "@/components/ui/button";

export function Layout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const logout = useMutation({
    mutationFn: async () => {
      unwrap(await api.POST("/api/auth/logout"));
    },
    onSuccess: () => {
      // Remove all data of the session from the cache.
      queryClient.clear();
      queryClient.setQueryData(authStateQuery.queryKey, { setup_required: false, logged_in: false });
      void navigate("/login");
    },
  });

  return (
    <div className="mx-auto flex min-h-svh max-w-5xl flex-col">
      <header className="flex items-center justify-between gap-2 border-b px-4 py-3">
        <span className="font-semibold">Watch Tower</span>
        <nav aria-label="Main" className="flex items-center gap-1">
          <Button asChild variant="ghost" size="sm">
            <Link to="/">Containers</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link to="/settings">Settings</Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={logout.isPending}
            onClick={() => {
              logout.mutate();
            }}
          >
            Log out
          </Button>
        </nav>
      </header>
      <main className="flex-1 px-4 py-4">
        <Outlet />
      </main>
    </div>
  );
}
