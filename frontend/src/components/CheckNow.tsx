// The last check time and the "Check now" button. The button is off during a run.
// The check events of the stream refetch the status.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import { checkStatusQuery } from "@/api/queries";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { formatTime } from "@/lib/time";

export function CheckNow() {
  const queryClient = useQueryClient();
  const { data } = useQuery(checkStatusQuery);
  const start = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/checks")),
    onSuccess: (status) => {
      queryClient.setQueryData(checkStatusQuery.queryKey, status);
    },
  });
  const running = data?.running ?? false;

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted-foreground">
          {running ? "Checking…" : `Last check: ${data?.last_run ? formatTime(data.last_run) : "never"}`}
        </span>
        <Button
          size="sm"
          disabled={data === undefined || running || start.isPending}
          onClick={() => {
            start.mutate();
          }}
        >
          Check now
        </Button>
      </div>
      <FormError error={start.error} />
    </div>
  );
}
