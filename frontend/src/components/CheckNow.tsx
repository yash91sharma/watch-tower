// The "Check now" button. Without `group`: the last check time and a button that checks all
// containers. With `group` (a group label): a small button that checks only that app.
// All buttons are off during a run. The check events of the stream refetch the status.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import { checkStatusQuery } from "@/api/queries";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { formatTime } from "@/lib/time";

export function CheckNow({ group }: { group?: string }) {
  const queryClient = useQueryClient();
  const { data } = useQuery(checkStatusQuery);
  const start = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/checks", { params: { query: group === undefined ? {} : { group } } })),
    onSuccess: (status) => {
      queryClient.setQueryData(checkStatusQuery.queryKey, status);
    },
  });
  const running = data?.running ?? false;
  const button = (
    <Button
      size="sm"
      variant={group === undefined ? "default" : "outline"}
      aria-label={group === undefined ? undefined : `Check now: ${group}`}
      disabled={data === undefined || running || start.isPending}
      onClick={() => {
        start.mutate();
      }}
    >
      Check now
    </Button>
  );

  if (group !== undefined) {
    return (
      <div className="flex flex-col items-end gap-1">
        {button}
        <FormError error={start.error} />
      </div>
    );
  }
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted-foreground">
          {running ? "Checking…" : `Last check: ${data?.last_run ? formatTime(data.last_run) : "never"}`}
        </span>
        {button}
      </div>
      <FormError error={start.error} />
    </div>
  );
}
