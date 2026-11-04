// What a page shows while its query has no data: the error, or a loading text.
import { FormError } from "@/components/FormError";

export function QueryPending({ error, text = "Loading…" }: { error: Error | null; text?: string }) {
  if (error) return <FormError error={error} />;
  return <p className="text-muted-foreground">{text}</p>;
}
