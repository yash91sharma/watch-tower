// A page section with an h2 title. Screen readers get the title as the section name.
// `actions` (for example buttons) show at the end of the title row.
import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Section({
  title,
  className,
  actions,
  children,
}: {
  title: string;
  className?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  const heading = (
    <h2 id={id} className="font-medium">
      {title}
    </h2>
  );
  return (
    <section aria-labelledby={id} className={cn("space-y-2", className)}>
      {actions ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          {heading}
          {actions}
        </div>
      ) : (
        heading
      )}
      {children}
    </section>
  );
}
