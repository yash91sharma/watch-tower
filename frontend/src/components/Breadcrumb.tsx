// The path to the current page, for example "Containers › web › Logs".
// Each part before the last is a link. The last part is the current page.
import { ChevronRight } from "lucide-react";
import { Link } from "react-router";

/** One part of the path. A part with no `to` is the current page. */
export interface Crumb {
  label: string;
  to?: string;
}

export function Breadcrumb({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
      <ol className="flex flex-wrap items-center gap-1">
        {crumbs.map((crumb, index) => (
          // The labels can repeat (a container named "Logs"), so the key is the position.
          <li key={index} className="flex items-center gap-1 break-all">
            {index > 0 && <ChevronRight aria-hidden className="size-3.5 shrink-0" />}
            {crumb.to === undefined ? (
              <span aria-current="page" className="text-foreground">
                {crumb.label}
              </span>
            ) : (
              <Link className="underline underline-offset-4 hover:text-foreground" to={crumb.to}>
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
