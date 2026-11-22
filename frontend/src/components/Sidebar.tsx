// The sidebar: the Compose groups and their containers, in API order, so that the admin
// can see and change the open container from each page.
// On a large screen the sidebar is open by default, and the browser keeps the choice of the
// admin in localStorage. On a small screen it is closed by default and closes when a page opens.
// The admin can collapse a group. The browser keeps the collapsed groups in localStorage.
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useMatch } from "react-router";

import { containersQuery } from "@/api/queries";
import { useCollapsed } from "@/lib/collapsed";
import { cn } from "@/lib/utils";

const openKey = "wt.sidebar";

/** True on a large screen (Tailwind `md` and up), where the sidebar is a column. */
function isLargeScreen() {
  return window.matchMedia("(min-width: 48rem)").matches;
}

/** The open state of the sidebar, for the toggle button and the sidebar. */
export function useSidebar() {
  const [open, setOpen] = useState(() => isLargeScreen() && localStorage.getItem(openKey) !== "closed");

  function toggle() {
    const next = !open;
    if (isLargeScreen()) localStorage.setItem(openKey, next ? "open" : "closed");
    setOpen(next);
  }

  /** Close the sidebar after a click on a link. Only on a small screen, where it covers the page. */
  function closeOnSmallScreen() {
    if (!isLargeScreen()) setOpen(false);
  }

  return { open, toggle, closeOnSmallScreen };
}

export function Sidebar({ id, onNavigate }: { id: string; onNavigate: () => void }) {
  const { data } = useQuery(containersQuery);
  // The container of the open page (its details or its logs), if there is one.
  const current = useMatch("/containers/:name/*")?.params.name;
  const groups = useCollapsed("wt.sidebarCollapsedGroups");

  return (
    <aside id={id} className="border-b bg-card md:w-60 md:shrink-0 md:border-r md:border-b-0">
      <nav aria-label="Container list" className="space-y-4 px-2 py-4 text-sm md:sticky md:top-0 md:max-h-svh md:overflow-y-auto">
        {data?.length === 0 && <p className="px-2 text-muted-foreground">No containers.</p>}
        {data?.map((group) => (
          <div key={group.label}>
            <button
              type="button"
              aria-expanded={groups.isOpen(group.label)}
              onClick={() => {
                groups.toggle(group.label);
              }}
              className="flex w-full items-center gap-1 rounded-md px-2 pb-1 text-left text-xs font-medium text-muted-foreground uppercase hover:text-foreground"
            >
              <ChevronRight
                aria-hidden
                className={cn("size-3.5 shrink-0 transition-transform", groups.isOpen(group.label) && "rotate-90")}
              />
              {group.label}
            </button>
            <ul hidden={!groups.isOpen(group.label)}>
              {group.containers.map((item) => (
                <li key={item.name}>
                  <Link
                    to={`/containers/${item.name}`}
                    onClick={onNavigate}
                    className={cn(
                      "block rounded-md px-2 py-1 break-all hover:bg-muted",
                      item.name === current && "bg-muted font-semibold",
                    )}
                  >
                    {item.name}
                  </Link>
                  {item.name === current && (
                    <ul className="my-1 ml-4 border-l pl-2">
                      <SubLink to={`/containers/${item.name}`} onNavigate={onNavigate}>
                        Details
                      </SubLink>
                      <SubLink to={`/containers/${item.name}/logs`} onNavigate={onNavigate}>
                        Logs
                      </SubLink>
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}

// A link to a page of the open container. It is marked when its page is open.
function SubLink({ to, onNavigate, children }: { to: string; onNavigate: () => void; children: string }) {
  return (
    <li>
      <NavLink
        to={to}
        end
        onClick={onNavigate}
        className="block rounded-md px-2 py-0.5 text-muted-foreground hover:bg-muted aria-[current=page]:text-foreground aria-[current=page]:underline aria-[current=page]:underline-offset-4"
      >
        {children}
      </NavLink>
    </li>
  );
}
