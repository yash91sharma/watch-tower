// The current CPU and memory of the apps and containers, with their 1-hour sparklines.
// The backend gives all values and labels. This only finds them by group label or name.
import { useQuery } from "@tanstack/react-query";

import { overviewQuery, sparklinesQuery } from "@/api/queries";
import type { ContainerUsage, GroupUsage, Sparkline as SparklineData } from "@/api/types";
import { Sparkline } from "@/components/Sparkline";

export function useUsage() {
  const { data: overview } = useQuery(overviewQuery);
  const { data: lines } = useQuery(sparklinesQuery);
  const groups = new Map<string, GroupUsage>(overview?.groups.map((group) => [group.label, group]));
  const containers = new Map<string, ContainerUsage>(
    overview?.groups.flatMap((group) => group.containers.map((item) => [item.name, item])),
  );
  return {
    overview,
    group: (label: string) => groups.get(label),
    container: (name: string) => containers.get(name),
    groupLine: (label: string): SparklineData | undefined => lines?.groups[label],
    containerLine: (name: string): SparklineData | undefined => lines?.containers[name],
  };
}

/** A sparkline of the last hour and the current value. */
export function UsageCell({ label, values, title }: { label: string | undefined; values: (number | null)[] | undefined; title: string }) {
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <Sparkline values={values ?? []} label={title} />
      <span>{label ?? "-"}</span>
    </div>
  );
}
