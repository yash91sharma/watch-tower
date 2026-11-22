// Page frame for the logged-in app: top nav, the sidebar, the page and a footer with the version.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut, PanelLeft } from "lucide-react";
import { useId, type ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { authStateQuery } from "@/api/queries";
import { version } from "../../package.json";

import { api, unwrap } from "@/api/client";
import { ConnectionBanner } from "@/components/ConnectionBanner";
import { Logo } from "@/components/Logo";
import { Sidebar, useSidebar } from "@/components/Sidebar";
import { Button } from "@/components/ui/button";

export function Layout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const sidebar = useSidebar();
  const sidebarId = useId();
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
        <div className="flex items-center justify-between gap-2 px-2 py-3 sm:px-4">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Sidebar"
              aria-expanded={sidebar.open}
              aria-controls={sidebar.open ? sidebarId : undefined}
              onClick={sidebar.toggle}
            >
              <PanelLeft aria-hidden />
            </Button>
            <Link to="/" className="flex items-center gap-2 rounded-md px-1 font-semibold">
              <Logo className="size-7" />
              {/* On a phone only the logo shows, so that the nav fits. */}
              <span className="max-sm:sr-only">WT</span>
            </Link>
          </div>
          <div className="flex items-center gap-1 sm:gap-2">
            <nav aria-label="Main" className="flex items-center gap-1">
              <NavItem to="/">Overview</NavItem>
              <NavItem to="/apps">Apps</NavItem>
              <NavItem to="/settings">Settings</NavItem>
            </nav>
            {/* Log out is an action, not a page: a line keeps it apart from the nav. */}
            <span aria-hidden className="h-5 w-px bg-border" />
            <Button
              variant="ghost"
              size="sm"
              aria-label="Log out"
              title="Log out"
              disabled={logout.isPending}
              onClick={() => {
                logout.mutate();
              }}
            >
              <LogOut aria-hidden />
              {/* On a phone only the icon shows, so that the nav fits. */}
              <span className="max-sm:hidden">Log out</span>
            </Button>
          </div>
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        {sidebar.open && <Sidebar id={sidebarId} onNavigate={sidebar.closeOnSmallScreen} />}
        <div className="mx-auto flex w-full max-w-5xl min-w-0 flex-1 flex-col">
          <ConnectionBanner />
          <main className="flex-1 px-4 py-6">
            <Outlet />
          </main>
        </div>
      </div>
      {/* The version of this build. The backend has the same version (a release test checks this). */}
      <footer className="border-t px-4 py-2 text-center text-xs text-muted-foreground">WT v{version}</footer>
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
