// One container: state, health, release source, update, events of the last 7 days, link to the logs.
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { containerQuery } from "@/api/queries";
import type { components } from "@/api/schema";
import { Breadcrumb } from "@/components/Breadcrumb";
import { HealthBadge } from "@/components/badges";
import { QueryPending } from "@/components/QueryPending";
import { ReleaseSource } from "@/components/ReleaseSource";
import { Section } from "@/components/Section";
import { UpdateBlock } from "@/components/UpdateBlock";
import { Button } from "@/components/ui/button";
import { formatTime } from "@/lib/time";

type ContainerDetail = components["schemas"]["ContainerDetail"];
type EventKind = components["schemas"]["EventKind"];

const eventText: Record<EventKind, string> = {
  became_unhealthy: "Unhealthy",
  recovered_health: "Healthy again",
  restart_loop: "Restart loop",
  recovered_loop: "Restart loop stopped",
};

export function ContainerPage() {
  const { name = "" } = useParams();
  const { data, error } = useQuery(containerQuery(name));

  return (
    <div className="space-y-6">
      <Breadcrumb crumbs={[{ label: "Containers", to: "/" }, { label: name }]} />
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
          <HealthBadge health={container.health} />
        </dd>
        <dt className="text-muted-foreground">Image</dt>
        <dd className="break-all">{container.image ?? "-"}</dd>
        <dt className="text-muted-foreground">Running</dt>
        <dd>{container.tag ?? "-"}</dd>
      </dl>
      <ReleaseSource name={container.name} source={container.release_source} confirmed={container.source_confirmed} />
      <UpdateBlock update={container.update} status={container.status} />
      <Section title="Events (last 7 days)">
        {container.events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No events in the last 7 days.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {container.events.map((event) => (
              <li key={`${event.time}-${event.kind}`}>
                {formatTime(event.time)}: {eventText[event.kind]}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </>
  );
}
