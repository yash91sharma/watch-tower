// App details: the container list. Compose groups in API order, one row per container,
// with the CPU and memory of each container and a Logs link (an icon next to the name).
// The admin can collapse a group, or expand or collapse all groups. The browser keeps the
// collapsed groups in localStorage.
// ?group=<label> (a link from the Overview) opens that group and scrolls to it.
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, ScrollText } from "lucide-react";
import { Link, useSearchParams } from "react-router";

import { containersQuery } from "@/api/queries";
import type { ContainerOut, Group } from "@/api/types";
import { AppGroup } from "@/components/AppGroup";
import { HealthBadge, StateLabel, StatusBadge } from "@/components/badges";
import { CheckNow } from "@/components/CheckNow";
import { ExpandCollapseAll } from "@/components/ExpandCollapseAll";
import { NoContainers } from "@/components/NoContainers";
import { QueryPending } from "@/components/QueryPending";
import { Button } from "@/components/ui/button";
import { type Usage, UsageCell, useUsage } from "@/components/Usage";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCollapsed } from "@/lib/collapsed";
import { usePageTitle } from "@/lib/pageTitle";

export function AppsPage() {
  usePageTitle("Apps");
  const { data, error } = useQuery(containersQuery);
  const focus = useSearchParams()[0].get("group");
  // The group of ?group= is open, also if it was collapsed.
  const groups = useCollapsed("wt.collapsedGroups", focus);
  const usage = useUsage();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Apps</h1>
        <div className="flex flex-wrap items-center gap-3">
          {data !== undefined && data.length > 0 && (
            <ExpandCollapseAll
              onExpand={groups.expandAll}
              onCollapse={() => {
                groups.collapseAll(data.map((group) => group.label));
              }}
            />
          )}
          <CheckNow />
        </div>
      </div>
      {data === undefined ? (
        <QueryPending error={error} text="Loading containers…" />
      ) : data.length === 0 ? (
        <NoContainers />
      ) : (
        data.map((group) => (
          <GroupTable
            key={group.label}
            group={group}
            usage={usage}
            open={groups.isOpen(group.label)}
            focus={group.label === focus}
            onToggle={() => {
              groups.toggle(group.label);
            }}
          />
        ))
      )}
    </div>
  );
}

// A column that a phone does not show (the container page has its value), so that the
// name, the health and the update fit with no side scroll.
const PHONE_HIDDEN = "max-sm:hidden";

function GroupTable({
  group,
  usage,
  open,
  focus,
  onToggle,
}: {
  group: Group;
  usage: Usage;
  open: boolean;
  focus: boolean;
  onToggle: () => void;
}) {
  return (
    <AppGroup
      label={group.label}
      count={group.containers.length}
      open={open}
      onToggle={onToggle}
      sums={usage.group(group.label)}
      update={group.update}
      focus={focus}
      actions={<CheckNow group={group.label} />}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className={PHONE_HIDDEN}>State</TableHead>
            <TableHead>Health</TableHead>
            <TableHead className={PHONE_HIDDEN}>CPU</TableHead>
            <TableHead className={PHONE_HIDDEN}>Memory</TableHead>
            <TableHead className={PHONE_HIDDEN}>Version</TableHead>
            <TableHead>Update</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {group.containers.map((item) => (
            <TableRow key={item.name} className="even:bg-muted/30">
              <TableCell className="max-sm:whitespace-normal">
                <div className="flex items-center gap-1">
                  <Link className="font-medium underline underline-offset-4 max-sm:break-all" to={`/containers/${item.name}`}>
                    {item.name}
                  </Link>
                  <Button asChild variant="ghost" size="icon-xs">
                    <Link to={`/containers/${item.name}/logs`} aria-label={`Logs of ${item.name}`} title="Logs">
                      <ScrollText aria-hidden />
                    </Link>
                  </Button>
                </div>
              </TableCell>
              <TableCell className={PHONE_HIDDEN}>
                <StateLabel state={item.state} />
              </TableCell>
              <TableCell>
                <HealthBadge health={item.health} label={item.health_label} />
              </TableCell>
              <TableCell className={PHONE_HIDDEN}>
                <UsageCell
                  label={usage.container(item.name)?.cpu_label}
                  values={usage.containerLine(item.name)?.cpu}
                  title={`CPU of ${item.name}, last hour`}
                />
              </TableCell>
              <TableCell className={PHONE_HIDDEN}>
                <UsageCell
                  label={usage.container(item.name)?.mem_used_label}
                  values={usage.containerLine(item.name)?.mem}
                  title={`Memory of ${item.name}, last hour`}
                />
              </TableCell>
              <TableCell className={PHONE_HIDDEN}>
                <Version item={item} />
              </TableCell>
              <TableCell>
                <StatusBadge status={item.status} label={item.status_label} severity={item.severity} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </AppGroup>
  );
}

/**
 * The version: "running → latest" when the API status is "update", else the running version.
 * The latest version links to its GitHub release (with no update, it is the running version).
 */
function Version({ item }: { item: ContainerOut }) {
  if (!item.latest_url) return item.tag ?? "-";
  const latest = (
    <a className="inline-flex items-center gap-1 underline underline-offset-4" href={item.latest_url} target="_blank" rel="noreferrer">
      {item.latest_version}
      <ExternalLink aria-hidden className="size-3.5 shrink-0" />
    </a>
  );
  if (item.status !== "update") return latest;
  return (
    <span className="inline-flex items-center gap-1">
      {item.tag ?? "-"} → {latest}
    </span>
  );
}
