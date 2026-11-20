// Overview (the home page): the resources of the Docker VM, the counts and the app list.
// The backend gives all values and labels. The VM charts use the shared range.
// The (i) button next to the title explains each metric.
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { overviewQuery, vmHistoryQuery } from "@/api/queries";
import type { Overview, VmOut } from "@/api/types";
import { ChartGrid } from "@/components/MetricChart";
import { MetricsHelp } from "@/components/MetricsHelp";
import { NoContainers } from "@/components/NoContainers";
import { QueryPending } from "@/components/QueryPending";
import { Section } from "@/components/Section";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { UsageCell, useUsage } from "@/components/Usage";
import { useMetricsRange } from "@/lib/metricsRange";

export function OverviewPage() {
  const { data, error } = useQuery(overviewQuery);
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-1">
        <h1 className="text-xl font-semibold">Overview</h1>
        <MetricsHelp />
      </div>
      {data === undefined ? <QueryPending error={error} /> : <OverviewBody overview={data} />}
    </div>
  );
}

function OverviewBody({ overview }: { overview: Overview }) {
  return (
    <>
      <div className="flex flex-wrap gap-3">
        <CountLink label={overview.counts.apps_label} />
        <CountLink label={overview.counts.containers_label} />
      </div>
      <Section title="Docker VM">
        {overview.vm ? (
          <VmTiles vm={overview.vm} />
        ) : (
          <p className="text-sm text-muted-foreground">No VM values yet. WT gets them at the next poll.</p>
        )}
        <VmCharts ranges={overview.ranges} />
      </Section>
      <AppList overview={overview} />
    </>
  );
}

function CountLink({ label }: { label: string }) {
  return (
    <Link to="/apps" className="rounded-xl border bg-card px-4 py-3 text-lg font-semibold shadow-xs hover:bg-muted">
      {label}
    </Link>
  );
}

function VmTiles({ vm }: { vm: VmOut }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Tile title="CPU" value={vm.cpu_label} percent={vm.cpu_percent} />
      <Tile title="Memory" value={vm.mem_label} percent={vm.mem_percent} detail={`Containers: ${vm.containers_mem_label}`} />
      <Tile title="Swap" value={vm.swap_label} percent={vm.swap_percent} />
      <Tile title="Disk" value={vm.disk_label} percent={vm.disk_percent} />
      <Tile title="Disk I/O" value={`Read ${vm.disk_read_label}, write ${vm.disk_write_label}`} />
      <Tile title="Network" value={`In ${vm.net_rx_label}, out ${vm.net_tx_label}`} />
      <Tile title="Load (1, 5, 15 min)" value={vm.load_label} />
      <Tile title="Uptime" value={vm.uptime_label} />
    </div>
  );
}

/** A current value, with a bar when the API gives a percent. */
function Tile({ title, value, percent, detail }: { title: string; value: string; percent?: number | null; detail?: string }) {
  return (
    <div className="space-y-1 rounded-xl border bg-card p-3 shadow-xs">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p className="text-sm font-medium">{value}</p>
      {percent !== undefined && percent !== null && (
        <div
          role="meter"
          aria-label={title}
          aria-valuenow={Math.round(percent)}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-1.5 overflow-hidden rounded-full bg-muted"
        >
          <div className="h-full rounded-full bg-series-1" style={{ width: `${String(Math.min(percent, 100))}%` }} />
        </div>
      )}
      {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
    </div>
  );
}

function VmCharts({ ranges }: { ranges: Overview["ranges"] }) {
  const [range] = useMetricsRange(ranges);
  const { data, error } = useQuery(vmHistoryQuery(range));
  if (data === undefined) return <QueryPending error={error} text="Loading charts…" />;
  return <ChartGrid history={data} ranges={ranges} />;
}

function AppList({ overview }: { overview: Overview }) {
  const usage = useUsage();
  return (
    <Section title="Apps">
      {overview.groups.length === 0 ? (
        <NoContainers className="text-sm" />
      ) : (
        <div className="rounded-xl border bg-card px-2 pb-1 shadow-xs">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>State</TableHead>
                <TableHead>CPU</TableHead>
                <TableHead>Memory</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {overview.groups.map((group) => [
                <TableRow key={`group-${group.label}`} className="bg-muted/40">
                  <TableCell>
                    <Link className="font-semibold underline underline-offset-4" to={`/apps?group=${encodeURIComponent(group.label)}`}>
                      {group.label}
                    </Link>
                  </TableCell>
                  <TableCell />
                  <TableCell>
                    <UsageCell label={group.cpu_label} values={usage.groupLine(group.label)?.cpu} title={`CPU of ${group.label}, last hour`} />
                  </TableCell>
                  <TableCell>
                    <UsageCell label={group.mem_label} values={usage.groupLine(group.label)?.mem} title={`Memory of ${group.label}, last hour`} />
                  </TableCell>
                </TableRow>,
                ...group.containers.map((item) => (
                  <TableRow key={item.name}>
                    <TableCell className="pl-6">
                      <Link className="underline underline-offset-4" to={`/containers/${item.name}`}>
                        {item.name}
                      </Link>
                    </TableCell>
                    <TableCell>{item.state}</TableCell>
                    <TableCell>
                      <UsageCell label={item.cpu_label} values={usage.containerLine(item.name)?.cpu} title={`CPU of ${item.name}, last hour`} />
                    </TableCell>
                    <TableCell>
                      <UsageCell label={item.mem_label} values={usage.containerLine(item.name)?.mem} title={`Memory of ${item.name}, last hour`} />
                    </TableCell>
                  </TableRow>
                )),
              ])}
            </TableBody>
          </Table>
        </div>
      )}
    </Section>
  );
}
