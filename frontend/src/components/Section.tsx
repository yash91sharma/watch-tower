// A page section with an h2 title. Screen readers get the title as the section name.
import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Section({ title, className, children }: { title: string; className?: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className={cn("space-y-2", className)}>
      <h2 id={id} className="font-medium">
        {title}
      </h2>
      {children}
    </section>
  );
}
