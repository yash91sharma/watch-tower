import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { RelativeTime } from "@/components/RelativeTime";
import { formatTime } from "@/lib/time";

beforeEach(() => {
  vi.useFakeTimers({ now: Date.parse("2026-11-21T12:00:00Z") });
});

afterEach(() => {
  vi.useRealTimers();
});

test("the time shows how long ago it was, and the full time on hover", () => {
  const iso = "2026-11-21T11:55:00Z";
  render(<RelativeTime iso={iso} />);

  const time = screen.getByText("5 minutes ago");
  expect(time.tagName).toBe("TIME");
  expect(time).toHaveAttribute("datetime", iso);
  expect(time).toHaveAttribute("title", formatTime(iso));
});

test("the text changes when time goes on", () => {
  render(<RelativeTime iso="2026-11-21T11:55:00Z" />);

  act(() => {
    vi.advanceTimersByTime(60_000);
  });

  expect(screen.getByText("6 minutes ago")).toBeInTheDocument();
});
