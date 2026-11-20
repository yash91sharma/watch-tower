// A list of terms and their values, in two columns (for example "State: running").
import { Fragment, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface Detail {
  term: string;
  value: ReactNode;
  /** Classes of the value, for example "break-all" for a long text. */
  className?: string;
}

export function DetailList({ items, className }: { items: Detail[]; className?: string }) {
  return (
    <dl className={cn("grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm", className)}>
      {items.map(({ term, value, className: valueClass }) => (
        <Fragment key={term}>
          <dt className="text-muted-foreground">{term}</dt>
          <dd className={valueClass}>{value}</dd>
        </Fragment>
      ))}
    </dl>
  );
}
