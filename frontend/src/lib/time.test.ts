import { expect, test } from "vitest";

import { formatAgo, formatTime } from "@/lib/time";

test("formatTime shows the time in the browser time zone", () => {
  const iso = "2026-01-01T12:30:00Z";

  expect(formatTime(iso)).toBe(new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
});

test("formatTime of null shows a dash", () => {
  expect(formatTime(null)).toBe("-");
});

const NOW = Date.parse("2026-11-21T12:00:00Z");
const before = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

test.each([
  [10, "just now"],
  [60, "1 minute ago"],
  [59 * 60, "59 minutes ago"],
  [3 * 3600, "3 hours ago"],
  [2 * 86400, "2 days ago"],
  [6 * 86400, "6 days ago"],
])("formatAgo of %i seconds ago is %s", (seconds, text) => {
  expect(formatAgo(before(seconds), NOW)).toBe(text);
});

test("formatAgo of 7 days or more shows the date", () => {
  const iso = before(7 * 86400);

  expect(formatAgo(iso, NOW)).toBe(formatTime(iso));
});
