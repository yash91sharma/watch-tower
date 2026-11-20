// An app group (a Compose project) as a card: a header and a body that the admin can collapse.
// The header has the toggle (a chevron and the group name), the CPU and memory sums, the
// container count and the buttons of the page. The page gives the body (its container table).
import { ChevronRight } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

import type { Group } from "@/api/types";
import { cn, plural } from "@/lib/utils";

// The header tint shows the update level of the group (the API decides the level).
const headerColor = { none: "bg-group-ok", update: "bg-group-update", critical: "bg-group-critical" } as const;

export interface AppGroupProps {
  label: string;
  /** The number of containers in the group. */
  count: number;
  open: boolean;
  onToggle: () => void;
  /** The CPU and memory sums of the group, when there are values. */
  sums?: { cpu_label: string; mem_label: string };
  /** The update level of the group. With no level, the header has no tint. */
  update?: Group["update"];
  /** 3 when the card is in a page section with an h2. */
  headingLevel?: 2 | 3;
  /** Scroll the card into view (for example for ?group=). */
  focus?: boolean;
  /** Buttons or links of the page, at the end of the header. */
  actions?: ReactNode;
  children: ReactNode;
}

export function AppGroup({ label, count, open, onToggle, sums, update, headingLevel = 2, focus = false, actions, children }: AppGroupProps) {
  const id = useId();
  const section = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focus) section.current?.scrollIntoView();
  }, [focus]);
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <section ref={section} aria-labelledby={id} className="overflow-hidden rounded-xl border bg-card shadow-xs">
      <div className={cn("flex flex-wrap items-center gap-2 px-2 py-1", update ? headerColor[update] : "bg-muted/40")}>
        <Heading id={id} className="min-w-0 flex-1 font-medium break-all">
          <button
            type="button"
            aria-expanded={open}
            aria-controls={`${id}-body`}
            onClick={onToggle}
            className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left hover:bg-muted"
          >
            <ChevronRight aria-hidden className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-90")} />
            {label}
          </button>
        </Heading>
        {sums && (
          // A fixed width: the sums of all groups are in one column, and the layout does not move when a value changes.
          <span className="hidden w-72 justify-end gap-3 pr-2 text-sm text-muted-foreground sm:flex">
            <span>CPU {sums.cpu_label}</span>
            <span>Memory {sums.mem_label}</span>
          </span>
        )}
        <span className="pr-2 text-sm text-muted-foreground">{plural(count, "container", "containers")}</span>
        {actions}
      </div>
      <div id={`${id}-body`} hidden={!open} className="border-t px-2 pb-1">
        {children}
      </div>
    </section>
  );
}
