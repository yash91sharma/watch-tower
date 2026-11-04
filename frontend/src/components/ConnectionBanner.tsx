// Live updates, and a banner while WT or Docker is not connected.
import { useEventStream } from "@/api/useEventStream";

export function ConnectionBanner() {
  const { wt, docker } = useEventStream();
  if (wt && docker) return null;
  return (
    <p role="status" className="bg-destructive-muted px-4 py-2 text-sm text-destructive">
      {wt ? "Docker is not connected. The data can be old." : "Watch Tower is not connected. Trying again…"}
    </p>
  );
}
