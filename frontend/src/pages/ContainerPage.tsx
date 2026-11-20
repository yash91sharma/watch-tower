// One container: state, health, resources, release source, update, events of the last 7 days, link to the logs.
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { containerHistoryQuery, containerQuery } from "@/api/queries";
import type { ContainerDetail } from "@/api/types";
import { Breadcrumb } from "@/components/Breadcrumb";
import { HealthBadge } from "@/components/badges";
import { ChartGrid } from "@/components/MetricChart";
import { QueryPending } from "@/components/QueryPending";
import { ReleaseSource } from "@/components/ReleaseSource";
import { Section } from "@/components/Section";
import { UpdateBlock } from "@/components/UpdateBlock";
import { useUsage } from "@/components/Usage";
import { Button } from "@/components/ui/button";
import { useMetricsRange } from "@/lib/metricsRange";
import { formatTime } from "@/lib/time";

export function ContainerPage() {
  const { name = "" } = useParams();
  const { data, error } = useQuery(containerQuery(name));

  return (
    <div className="space-y-6">
      <Breadcrumb crumbs={[{ label: "Apps", to: "/apps" }, { label: name }]} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold break-all">{name}</h1>
        <Button asChild variant="outline" size="sm">
          <Link to={`/containers/${name}/logs`}>Logs</Link>
        </Button>
      </div>
      {data === undefined ? <QueryPending error={error} /> : <Details container={data} />}
    </div>
  );
}

function Details({ container }: { container: ContainerDetail }) {
  return (
    <>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-muted-foreground">State</dt>
        <dd>{container.state}</dd>
        <dt className="text-muted-foreground">Health</dt>
        <dd>
          <HealthBadge health={container.health} label={container.health_label} />
        </dd>
        <dt className="text-muted-foreground">Image</dt>
        <dd className="break-all">{container.image ?? "-"}</dd>
        <dt className="text-muted-foreground">Running</dt>
        <dd>{container.tag ?? "-"}</dd>
      </dl>
      <Resources name={container.name} />
      <ReleaseSource name={container.name} source={container.release_source} confirmed={container.source_confirmed} />
      <UpdateBlock update={container.update} status={container.status} />
      <Section title="Events (last 7 days)">
        {container.events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No events in the last 7 days.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {container.events.map((event) => (
              <li key={`${event.time}-${event.kind}`}>
                {formatTime(event.time)}: {event.label}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </>
  );
}

/** The current values (from the overview) and the charts of the container, with the shared range. */
function Resources({ name }: { name: string }) {
  const usage = useUsage();
  const current = usage.container(name);
  const ranges = usage.overview?.ranges ?? [];
  const [range] = useMetricsRange(ranges);
  const { data, error } = useQuery(containerHistoryQuery(name, range));
  return (
    <Section title="Resources">
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-muted-foreground">CPU</dt>
        <dd>{current?.cpu_label ?? "-"}</dd>
        <dt className="text-muted-foreground">Memory</dt>
        <dd>{current?.mem_label ?? "-"}</dd>
        <dt className="text-muted-foreground">Network</dt>
        <dd>{current ? `In ${current.net_rx_label}, out ${current.net_tx_label}` : "-"}</dd>
        <dt className="text-muted-foreground">Disk I/O</dt>
        <dd>{current ? `Read ${current.disk_read_label}, write ${current.disk_write_label}` : "-"}</dd>
      </dl>
      {data === undefined ? (
        <QueryPending error={error} text="Loading charts…" />
      ) : (
        <ChartGrid history={data} ranges={ranges} />
      )}
    </Section>
  );
}
