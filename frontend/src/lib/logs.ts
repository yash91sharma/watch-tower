// Log lines in the browser: parse the SSE data and keep a buffer with a size limit.

/** A log line from the SSE (LogLineOut in the backend; the OpenAPI schema has no SSE types). */
interface LogLineOut {
  time: string | null;
  stream: "stdout" | "stderr";
  text: string;
}

/** A log line with an id for the list key. */
export type LogLine = LogLineOut & { id: number };

/** The buffer keeps the newest lines only. */
export const MAX_LINES = 10_000;

export function parseLine(data: string, id: number): LogLine {
  return { ...(JSON.parse(data) as LogLineOut), id };
}

export function appendLines(lines: LogLine[], newLines: LogLine[]): LogLine[] {
  const all = lines.concat(newLines);
  return all.length > MAX_LINES ? all.slice(-MAX_LINES) : all;
}
