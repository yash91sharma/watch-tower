// Badges for the container health and the update severity.
import type { components } from "@/api/schema";
import { Badge } from "@/components/ui/badge";

type Health = components["schemas"]["ContainerOut"]["health"];
type Severity = components["schemas"]["Severity"];

const healthVariant = { healthy: "secondary", unhealthy: "destructive", starting: "outline", none: "outline" } as const;

export function HealthBadge({ health }: { health: Health }) {
  return <Badge variant={healthVariant[health]}>{health === "none" ? "no healthcheck" : health}</Badge>;
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (severity === null) return null;
  return <Badge variant={severity === "critical" ? "destructive" : "secondary"}>{severity}</Badge>;
}
