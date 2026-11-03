// Page frame for the logged-in app: top nav and the page below it.
import { Link, Outlet } from "react-router";

import { Button } from "@/components/ui/button";

export function Layout() {
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
          <Button variant="outline" size="sm">
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
