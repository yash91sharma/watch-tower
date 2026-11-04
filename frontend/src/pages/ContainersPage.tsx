// The container list: Compose groups in API order, one row per container.
// The admin can collapse a group. The browser keeps the collapsed groups in localStorage.
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router";

import { containersQuery } from "@/api/queries";
import type { components } from "@/api/schema";
import { HealthBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import { CheckNow } from "@/components/CheckNow";
import { QueryPending } from "@/components/QueryPending";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn, plural } from "@/lib/utils";

type Group = components["schemas"]["GroupOut"];

const collapsedKey = "wt.collapsedGroups";

function readCollapsed() {
  return JSON.parse(localStorage.getItem(collapsedKey) ?? "[]") as string[];
}

export function ContainersPage() {
  const { data, error } = useQuery(containersQuery);
  const [collapsed, setCollapsed] = useState(readCollapsed);

  function toggle(label: string) {
    const next = collapsed.includes(label) ? collapsed.filter((item) => item !== label) : [...collapsed, label];
    localStorage.setItem(collapsedKey, JSON.stringify(next));
    setCollapsed(next);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Containers</h1>
        <CheckNow />
      </div>
      {data === undefined ? (
        <QueryPending error={error} text="Loading containers…" />
      ) : data.length === 0 ? (
        <p className="text-muted-foreground">
          No containers. WT shows all containers on this Docker host, except the containers with the label{" "}
          <code>wt.enable=false</code>.
        </p>
      ) : (
        data.map((group) => (
          <GroupTable
            key={group.label}
            group={group}
            open={!collapsed.includes(group.label)}
            onToggle={() => {
              toggle(group.label);
            }}
          />
        ))
      )}
    </div>
  );
}

function GroupTable({ group, open, onToggle }: { group: Group; open: boolean; onToggle: () => void }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="rounded-xl border bg-card shadow-xs">
      <div className="flex items-center gap-2 px-2 py-1">
        <h2 id={id} className="flex-1 font-medium">
          <button
            type="button"
            aria-expanded={open}
            aria-controls={`${id}-table`}
            onClick={onToggle}
            className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left hover:bg-muted"
          >
            <ChevronRight
              aria-hidden
              className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-90")}
            />
            {group.label}
          </button>
        </h2>
        <span className="pr-2 text-sm text-muted-foreground">
          {plural(group.containers.length, "container", "containers")}
        </span>
      </div>
      <div id={`${id}-table`} hidden={!open} className="border-t px-2 pb-1">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Health</TableHead>
              <TableHead>Running</TableHead>
              <TableHead>Latest</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Severity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {group.containers.map((item) => (
              <TableRow key={item.name}>
                <TableCell>
                  <Link className="font-medium underline-offset-4 hover:underline" to={`/containers/${item.name}`}>
                    {item.name}
                  </Link>
                </TableCell>
                <TableCell>{item.state}</TableCell>
                <TableCell>
                  <HealthBadge health={item.health} />
                </TableCell>
                <TableCell>{item.tag ?? "-"}</TableCell>
                <TableCell>{item.latest_version ?? "-"}</TableCell>
                <TableCell>
                  <StatusBadge status={item.status} />
                </TableCell>
                <TableCell>
                  <SeverityBadge severity={item.severity} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}
