import { expect, test } from "vitest";

import {
  appendLines,
  highlight,
  type LogLine,
  matchingLines,
  MAX_LINES,
  parseLine,
  prettyJson,
} from "@/lib/logs";

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

const texts = ["GET /health 200", "ERROR db timeout", "get /api 500", "done"].map(
  (text, id): LogLine => ({ id, time: null, stream: "stdout", text }),
);

test("matchingLines gives the lines with the query, not case-sensitive", () => {
  expect(matchingLines(texts, "get").map((item) => item.id)).toEqual([0, 2]);
  expect(matchingLines(texts, "ERROR").map((item) => item.id)).toEqual([1]);
});

test("matchingLines gives no lines for no match or an empty query", () => {
  expect(matchingLines(texts, "nothing")).toEqual([]);
  expect(matchingLines(texts, "")).toEqual([]);
});

test("highlight marks each match, not case-sensitive", () => {
  expect(highlight("Get a get", "GET")).toEqual([
    { text: "Get", match: true },
    { text: " a ", match: false },
    { text: "get", match: true },
  ]);
});

test("highlight with no match or no query gives the text", () => {
  expect(highlight("plain", "x")).toEqual([{ text: "plain", match: false }]);
  expect(highlight("plain", "")).toEqual([{ text: "plain", match: false }]);
});

test("prettyJson formats a JSON object line", () => {
  expect(prettyJson(' {"level":"info","n":1} ')).toBe('{\n  "level": "info",\n  "n": 1\n}');
});

test("prettyJson does not change bad JSON, plain text or other JSON values", () => {
  expect(prettyJson('{"level": "info"')).toBe('{"level": "info"');
  expect(prettyJson("plain text")).toBe("plain text");
  expect(prettyJson("[1, 2]")).toBe("[1, 2]");
  expect(prettyJson("42")).toBe("42");
});
