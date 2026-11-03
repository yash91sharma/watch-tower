import { expect, test } from "vitest";

import { appendLines, type LogLine, MAX_LINES, parseLine } from "@/lib/logs";

function line(id: number): LogLine {
  return { id, time: null, stream: "stdout", text: `line ${String(id)}` };
}

test("parseLine reads the SSE data and adds the id", () => {
  const data = JSON.stringify({ time: "2026-11-02T06:00:00Z", stream: "stderr", text: "boom" });

  expect(parseLine(data, 7)).toEqual({ id: 7, time: "2026-11-02T06:00:00Z", stream: "stderr", text: "boom" });
});

test("appendLines adds the new lines at the end", () => {
  expect(appendLines([line(1)], [line(2), line(3)]).map((item) => item.id)).toEqual([1, 2, 3]);
});

test("appendLines keeps the newest MAX_LINES lines", () => {
  const old = Array.from({ length: MAX_LINES }, (_, index) => line(index));

  const lines = appendLines(old, [line(MAX_LINES), line(MAX_LINES + 1)]);

  expect(MAX_LINES).toBe(10_000);
  expect(lines).toHaveLength(MAX_LINES);
  expect(lines[0]?.id).toBe(2);
  expect(lines.at(-1)?.id).toBe(MAX_LINES + 1);
});
