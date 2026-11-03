import { expect, test } from "vitest";

import { formatTime } from "@/lib/time";

test("formatTime shows the time in the browser time zone", () => {
  const iso = "2026-01-01T12:30:00Z";

  expect(formatTime(iso)).toBe(new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
});

test("formatTime of null shows a dash", () => {
  expect(formatTime(null)).toBe("-");
});
