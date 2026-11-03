// The current update of a container. Summary and release notes show as plain text only
// (React escapes them; never use them as HTML).
import { useId } from "react";

import type { components } from "@/api/schema";
import { SeverityBadge } from "@/components/badges";

type Update = components["schemas"]["UpdateOut"];
type Status = components["schemas"]["Status"];

export function UpdateBlock({ update, status }: { update: Update | null; status: Status }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="space-y-2">
      <h2 id={id} className="font-medium">
        Update
      </h2>
      {update === null ? (
        <p className="text-sm text-muted-foreground">No update. Status: {status}.</p>
      ) : (
        <>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Running</dt>
            <dd>{update.from_version}</dd>
            <dt className="text-muted-foreground">Latest</dt>
            <dd>{update.to_version}</dd>
            <dt className="text-muted-foreground">Severity</dt>
            <dd>
              <SeverityBadge severity={update.severity} />
            </dd>
          </dl>
          {update.summary && <p className="text-sm">{update.summary}</p>}
          <pre
            data-testid="release-notes"
            className="max-h-96 overflow-auto rounded-lg border bg-muted/50 p-3 font-mono text-xs whitespace-pre-wrap"
          >
            {update.release_notes}
          </pre>
        </>
      )}
    </section>
  );
}
