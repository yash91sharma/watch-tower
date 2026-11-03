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

/** The lines with the query. Not case-sensitive. An empty query matches no line. */
export function matchingLines(lines: LogLine[], query: string): LogLine[] {
  const needle = query.toLowerCase();
  if (!needle) return [];
  return lines.filter((line) => line.text.toLowerCase().includes(needle));
}

/** The text in parts, with each match of the query marked. Not case-sensitive. */
export function highlight(text: string, query: string): { text: string; match: boolean }[] {
  const needle = query.toLowerCase();
  if (!needle) return [{ text, match: false }];
  const lower = text.toLowerCase();
  const parts: { text: string; match: boolean }[] = [];
  let start = 0;
  for (let at = lower.indexOf(needle); at !== -1; at = lower.indexOf(needle, start)) {
    if (at > start) parts.push({ text: text.slice(start, at), match: false });
    parts.push({ text: text.slice(at, at + needle.length), match: true });
    start = at + needle.length;
  }
  if (start < text.length || parts.length === 0) parts.push({ text: text.slice(start), match: false });
  return parts;
}

/** A JSON object line, formatted. Other lines (bad JSON, plain text, arrays) do not change. */
export function prettyJson(text: string): string {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{")) return text;
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return text;
  }
}
