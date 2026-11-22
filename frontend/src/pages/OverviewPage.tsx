// Overview (the home page): the resources of the Docker VM, the counts and the app list.
// The backend gives all values and labels. The VM charts use the shared range.
// The (i) button next to the title explains each metric.
// The admin can collapse an app group, or expand or collapse all groups. The browser keeps
// the collapsed groups in localStorage.
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router";

import { overviewQuery, vmHistoryQuery } from "@/api/queries";
import type { GroupUsage, Overview, VmOut } from "@/api/types";
import { AppGroup } from "@/components/AppGroup";
import { StateLabel } from "@/components/badges";
import { ExpandCollapseAll } from "@/components/ExpandCollapseAll";
import { HistoryCharts } from "@/components/MetricChart";
import { MetricsHelp } from "@/components/MetricsHelp";
import { NoContainers } from "@/components/NoContainers";
import { QueryPending } from "@/components/QueryPending";
import { Section } from "@/components/Section";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type Usage, UsageCell, useUsage } from "@/components/Usage";
import { useCollapsed } from "@/lib/collapsed";
import { usePageTitle } from "@/lib/pageTitle";

export function OverviewPage() {
  usePageTitle("Overview");
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
        <HistoryCharts ranges={overview.ranges} query={vmHistoryQuery} />
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
      <Tile title="Disk I/O" value={vm.disk_io_label} />
      <Tile title="Network" value={vm.network_label} />
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

function AppList({ overview }: { overview: Overview }) {
  const groups = useCollapsed("wt.overviewCollapsedGroups");
  const usage = useUsage();
  return (
    <Section
      title="Apps"
      actions={
        overview.groups.length > 0 && (
          <ExpandCollapseAll
            onExpand={groups.expandAll}
            onCollapse={() => {
              groups.collapseAll(overview.groups.map((group) => group.label));
            }}
          />
        )
      }
    >
      {overview.groups.length === 0 ? (
        <NoContainers className="text-sm" />
      ) : (
        <div className="space-y-3">
          {overview.groups.map((group) => (
            <GroupCard
              key={group.label}
              group={group}
              usage={usage}
              open={groups.isOpen(group.label)}
              onToggle={() => {
                groups.toggle(group.label);
              }}
            />
          ))}
        </div>
      )}
    </Section>
  );
}

/** An app group: the shared card with the sums, a link to the group on Apps and one row per container. */
function GroupCard({
  group,
  usage,
  open,
  onToggle,
}: {
  group: GroupUsage;
  usage: Usage;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <AppGroup
      label={group.label}
      count={group.containers.length}
      open={open}
      onToggle={onToggle}
      sums={group}
      headingLevel={3}
      actions={
        <Button asChild variant="ghost" size="icon-xs">
          <Link to={`/apps?group=${encodeURIComponent(group.label)}`} aria-label={`Open ${group.label} on the Apps page`} title="Apps page">
            <ArrowUpRight aria-hidden />
          </Link>
        </Button>
      }
    >
      {/* Fixed column widths: the columns of all group cards line up. The minimum width keeps
          the columns apart on a phone (the table scrolls to the side). */}
      <Table className="min-w-2xl table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40%]">Name</TableHead>
            <TableHead className="w-[14%]">State</TableHead>
            <TableHead className="w-[23%]">CPU</TableHead>
            <TableHead className="w-[23%]">Memory</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {group.containers.map((item) => (
            <TableRow key={item.name}>
              <TableCell className="break-all whitespace-normal">
                <Link className="underline underline-offset-4" to={`/containers/${item.name}`}>
                  {item.name}
                </Link>
              </TableCell>
              <TableCell>
                <StateLabel state={item.state} />
              </TableCell>
              <TableCell>
                <UsageCell label={item.cpu_label} values={usage.containerLine(item.name)?.cpu} title={`CPU of ${item.name}, last hour`} />
              </TableCell>
              <TableCell>
                <UsageCell label={item.mem_label} values={usage.containerLine(item.name)?.mem} title={`Memory of ${item.name}, last hour`} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AppGroup>
  );
}
