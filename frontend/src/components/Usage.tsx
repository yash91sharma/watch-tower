// The current CPU and memory of the apps and containers, with their 1-hour sparklines.
// The backend gives all values and labels. This only finds them by group label or name.
import { useQuery } from "@tanstack/react-query";

import { overviewQuery, sparklinesQuery } from "@/api/queries";
import type { ContainerUsage, GroupUsage, Sparkline as SparklineData } from "@/api/types";
import { Sparkline } from "@/components/Sparkline";

/** The lookups of a page. Call useUsage once per page and give the result to the rows. */
export type Usage = ReturnType<typeof useUsage>;

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
    containerLine: (name: string): SparklineData | undefined => lines?.containers[name],
  };
}

/** The current value, with the sparkline of the last hour under it (narrow table columns). */
export function UsageCell({ label, values, title }: { label: string | undefined; values: (number | null)[] | undefined; title: string }) {
  return (
    <div className="flex flex-col items-start gap-1 whitespace-nowrap">
      <span>{label ?? "-"}</span>
      <Sparkline values={values ?? []} label={title} />
    </div>
  );
}
