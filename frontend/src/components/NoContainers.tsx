// The text of a page with no containers to show.
import { cn } from "@/lib/utils";

export function NoContainers({ className }: { className?: string }) {
  return (
    <p className={cn("text-muted-foreground", className)}>
      No containers. WT shows all containers on this Docker host, except the containers with the label{" "}
      <code>wt.enable=false</code>.
    </p>
  );
}
