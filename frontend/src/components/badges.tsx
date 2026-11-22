// Badges for the container health, the update severity and the update status, and a dot for
// the Docker state. The API gives the text; the badge picks only the color.
// Colors: success = good, warning = wait, destructive = needs action, info = update, outline = no data.
import type { Health, Severity, Status } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const healthVariant = { healthy: "success", unhealthy: "destructive", starting: "warning", none: "outline" } as const;

const statusVariant = {
  update: "info",
  "up to date": "success",
  error: "destructive",
  "no check": "outline",
  "no source": "outline",
  "not checked": "outline",
} as const;

export function HealthBadge({ health, label }: { health: Health; label: string }) {
  return <Badge variant={healthVariant[health]}>{label}</Badge>;
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (severity === null) return null;
  return <Badge variant={severity === "critical" ? "destructive" : "info"}>{severity}</Badge>;
}

/** The update status. A critical update has the destructive color, so one badge tells all. */
export function StatusBadge({ status, label, severity = null }: { status: Status; label: string; severity?: Severity | null }) {
  const variant = status === "update" && severity === "critical" ? "destructive" : statusVariant[status];
  return <Badge variant={variant}>{label}</Badge>;
}

// The Docker states that have a color. Other states (paused, created, removing) are grey.
const stateVariant: Record<string, "success" | "warning" | "destructive"> = {
  running: "success",
  restarting: "warning",
  exited: "destructive",
  dead: "destructive",
};

const dotColor = { success: "bg-success", warning: "bg-warning", destructive: "bg-destructive", outline: "bg-muted-foreground" } as const;

/** The Docker state as a colored dot and its text. Calmer than a badge, because most rows are "running". */
export function StateLabel({ state }: { state: string }) {
  const variant = stateVariant[state] ?? "outline";
  return (
    <span data-variant={variant} className="inline-flex items-center gap-1.5">
      <span aria-hidden className={cn("size-2 shrink-0 rounded-full", dotColor[variant])} />
      {state}
    </span>
  );
}
