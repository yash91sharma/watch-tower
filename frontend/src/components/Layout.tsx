// Page frame for the logged-in app: top nav and the page below it.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { authStateQuery } from "@/api/queries";
import { api, unwrap } from "@/api/client";
import { ConnectionBanner } from "@/components/ConnectionBanner";
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
    <div className="flex min-h-svh flex-col">
      <header className="border-b bg-header">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 rounded-md font-semibold">
            <img src="/icon.svg" alt="" className="size-6" />
            WT
          </Link>
          <nav aria-label="Main" className="flex items-center gap-1">
            <NavItem to="/">Containers</NavItem>
            <NavItem to="/settings">Settings</NavItem>
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
        </div>
      </header>
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col">
        <ConnectionBanner />
        <main className="flex-1 px-4 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

// A nav link. It has a quiet raised look when its page is open.
function NavItem({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Button asChild variant="ghost" size="sm">
      <NavLink to={to} end className="aria-[current=page]:bg-card aria-[current=page]:shadow-xs dark:aria-[current=page]:bg-accent">
        {children}
      </NavLink>
    </Button>
  );
}
