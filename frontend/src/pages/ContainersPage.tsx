// The container list: Compose groups in API order, one row per container.
import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link } from "react-router";

import { containersQuery } from "@/api/queries";
import type { components } from "@/api/schema";
import { HealthBadge, SeverityBadge } from "@/components/badges";
import { CheckNow } from "@/components/CheckNow";
import { FormError } from "@/components/FormError";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type Group = components["schemas"]["GroupOut"];

export function ContainersPage() {
  const { data, error } = useQuery(containersQuery);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Containers</h1>
        <CheckNow />
      </div>
      {data === undefined ? (
        error ? (
          <FormError error={error} />
        ) : (
          <p className="text-muted-foreground">Loading containers…</p>
        )
      ) : data.length === 0 ? (
        <p className="text-muted-foreground">
          No containers. WT shows all containers on this Docker host, except the containers with the label{" "}
          <code>wt.enable=false</code>.
        </p>
      ) : (
        data.map((group) => <GroupTable key={group.label} group={group} />)
      )}
    </div>
  );
}

function GroupTable({ group }: { group: Group }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="space-y-2">
      <h2 id={id} className="font-medium">
        {group.label}
      </h2>
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
              <TableCell>{item.status}</TableCell>
              <TableCell>
                <SeverityBadge severity={item.severity} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
