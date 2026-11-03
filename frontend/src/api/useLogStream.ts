// The log SSE of a container, as a buffer of lines. New lines go into the buffer once
// per animation frame, so that a fast log does not render for each line.
import { useEffect, useState } from "react";

import { appendLines, type LogLine, parseLine } from "@/lib/logs";

export function useLogStream(name: string, tail: number): { lines: LogLine[]; error: string | null } {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const source = new EventSource(`/api/containers/${encodeURIComponent(name)}/logs?tail=${String(tail)}`);
    let pending: LogLine[] = [];
    let frame: number | null = null;
    let nextId = 0;

    function flush() {
      const batch = pending;
      pending = [];
      frame = null;
      setLines((current) => appendLines(current, batch));
    }

    // The browser connects again after a network error, and WT sends the tail again.
    // So start with an empty buffer on each open: no duplicate lines.
    source.addEventListener("open", () => {
      pending = [];
      setLines([]);
      setError(null);
    });
    source.addEventListener("message", (event: MessageEvent<string>) => {
      pending.push(parseLine(event.data, nextId++));
      frame ??= requestAnimationFrame(flush);
    });
    // WT sends an "error" event with a text (for example, Docker is not connected).
    // A connection error has no data.
    source.addEventListener("error", (event: Event) => {
      if (event instanceof MessageEvent && typeof event.data === "string") {
        setError(JSON.parse(event.data) as string);
      }
    });

    return () => {
      source.close();
      if (frame !== null) cancelAnimationFrame(frame);
    };
  }, [name, tail]);

  return { lines, error };
}
