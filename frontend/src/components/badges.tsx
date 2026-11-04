// Badges for the container health, the update severity and the update status.
// Colors: success = good, warning = wait, destructive = needs action, info = update, outline = no data.
import type { components } from "@/api/schema";
import { Badge } from "@/components/ui/badge";

type Health = components["schemas"]["ContainerOut"]["health"];
type Severity = components["schemas"]["Severity"];
type Status = components["schemas"]["Status"];

const healthVariant = { healthy: "success", unhealthy: "destructive", starting: "warning", none: "outline" } as const;

const statusVariant = {
  update: "info",
  "up to date": "success",
  error: "destructive",
  "no check": "outline",
  "no source": "outline",
  "not checked": "outline",
} as const;

export function HealthBadge({ health }: { health: Health }) {
  return <Badge variant={healthVariant[health]}>{health === "none" ? "no healthcheck" : health}</Badge>;
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (severity === null) return null;
  return <Badge variant={severity === "critical" ? "destructive" : "info"}>{severity}</Badge>;
}

export function StatusBadge({ status }: { status: Status }) {
  return <Badge variant={statusVariant[status]}>{status}</Badge>;
}
