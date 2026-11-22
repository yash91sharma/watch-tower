// One container: state, health, resources, release source, update, events of the last 7 days, link to the logs.
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { containerHistoryQuery, containerQuery } from "@/api/queries";
import type { ContainerDetail } from "@/api/types";
import { Breadcrumb } from "@/components/Breadcrumb";
import { DetailList } from "@/components/DetailList";
import { HealthBadge, StateLabel } from "@/components/badges";
import { HistoryCharts } from "@/components/MetricChart";
import { QueryPending } from "@/components/QueryPending";
import { ReleaseSource } from "@/components/ReleaseSource";
import { Section } from "@/components/Section";
import { UpdateBlock } from "@/components/UpdateBlock";
import { useUsage } from "@/components/Usage";
import { Button } from "@/components/ui/button";
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
      <DetailList
        items={[
          { term: "State", value: <StateLabel state={container.state} /> },
          { term: "Health", value: <HealthBadge health={container.health} label={container.health_label} /> },
          { term: "Image", value: container.image ?? "-", className: "break-all" },
          { term: "Running", value: container.tag ?? "-" },
        ]}
      />
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
  return (
    <Section title="Resources">
      <DetailList
        items={[
          { term: "CPU", value: current?.cpu_label ?? "-" },
          { term: "Memory", value: current?.mem_label ?? "-" },
          { term: "Network", value: current?.network_label ?? "-" },
          { term: "Disk I/O", value: current?.disk_io_label ?? "-" },
        ]}
      />
      <HistoryCharts ranges={usage.overview?.ranges ?? []} query={(range) => containerHistoryQuery(name, range)} />
    </Section>
  );
}
