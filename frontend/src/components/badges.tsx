// Badges for the container health, the update severity and the update status. The API gives
// the label text; the badge picks only the color.
// Colors: success = good, warning = wait, destructive = needs action, info = update, outline = no data.
import type { Health, Severity, Status } from "@/api/types";
import { Badge } from "@/components/ui/badge";

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

export function StatusBadge({ status, label }: { status: Status; label: string }) {
  return <Badge variant={statusVariant[status]}>{label}</Badge>;
}
