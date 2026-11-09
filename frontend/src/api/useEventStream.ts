// Live updates from GET /api/stream. The events only name what changed, so the hook
// refetches the matching queries. It also gives the WT and Docker connection state.
import { type QueryKey, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { authStateQuery, checkStatusQuery, containersQuery } from "@/api/queries";

const RETRY_MS = 3000;

export function useEventStream(): { wt: boolean; docker: boolean } {
  const queryClient = useQueryClient();
  const [wt, setWt] = useState(true);
  const [docker, setDocker] = useState(true);

  useEffect(() => {
    let source: EventSource;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let lost = false;
    const refetch = (queryKey: QueryKey) => void queryClient.invalidateQueries({ queryKey });

    function connect() {
      source = new EventSource("/api/stream");
      source.addEventListener("open", () => {
        setWt(true);
        // The UI can have missed events while it was not connected: get all data again.
        if (lost) void queryClient.invalidateQueries();
        lost = false;
      });
      // The browser does not connect again after an HTTP error (for example a 502 while
      // WT restarts). So close the stream and connect again here, for all errors.
      source.addEventListener("error", () => {
        source.close();
        lost = true;
        setWt(false);
        // EventSource does not give the status. If the session is gone (401), the new auth
        // state makes the auth guard open /login. That unmount stops the retry.
        void queryClient.invalidateQueries({ queryKey: authStateQuery.queryKey });
        retry = setTimeout(connect, RETRY_MS);
      });
      source.addEventListener("container", () => {
        refetch(containersQuery.queryKey);
      });
      source.addEventListener("check", () => {
        refetch(checkStatusQuery.queryKey);
        refetch(containersQuery.queryKey);
      });
      source.addEventListener("docker", (event: MessageEvent<string>) => {
        const { connected } = JSON.parse(event.data) as { connected: boolean };
        setDocker(connected);
        if (connected) refetch(containersQuery.queryKey);
      });
    }

    connect();
    return () => {
      clearTimeout(retry);
      source.close();
    };
  }, [queryClient]);

  return { wt, docker };
}
