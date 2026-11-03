import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { LogView } from "@/components/LogView";
import type { LogLine } from "@/lib/logs";

function lines(count: number, stream: LogLine["stream"] = "stdout"): LogLine[] {
  return Array.from({ length: count }, (_, id) => ({ id, time: null, stream, text: `line ${String(id)}` }));
}

// TanStack Virtual reads the size of the scroll element (client size) and of each row
// (offsetHeight). jsdom gives 0, so no row shows.
beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(20);
});
afterEach(() => {
  vi.restoreAllMocks();
});

/** jsdom has no layout: give the scroll element fixed sizes and a working scrollTop. */
function fakeScroll(element: HTMLElement) {
  let top = 0;
  Object.defineProperty(element, "scrollHeight", { configurable: true, value: 1000 });
  Object.defineProperty(element, "clientHeight", { configurable: true, value: 100 });
  Object.defineProperty(element, "scrollTop", {
    configurable: true,
    get: () => top,
    set: (value: number) => {
      top = Math.min(value, 900);
    },
  });
}

test("the view shows the lines, stderr in another color", () => {
  render(<LogView lines={[...lines(1), { id: 1, time: null, stream: "stderr", text: "boom" }]} />);

  expect(screen.getByText("line 0")).not.toHaveClass("text-destructive");
  expect(screen.getByText("boom")).toHaveClass("text-destructive");
});

test("follow mode scrolls to the end when new lines come", () => {
  const { rerender } = render(<LogView lines={lines(2)} />);
  const log = screen.getByRole("log");
  fakeScroll(log);

  rerender(<LogView lines={lines(3)} />);

  expect(log.scrollTop).toBe(900);
  expect(screen.queryByRole("button", { name: "Follow" })).not.toBeInTheDocument();
});

test("scroll up pauses follow. The button starts it again", async () => {
  const user = userEvent.setup();
  const { rerender } = render(<LogView lines={lines(2)} />);
  const log = screen.getByRole("log");
  fakeScroll(log);

  log.scrollTop = 200;
  fireEvent.scroll(log);
  rerender(<LogView lines={lines(3)} />);

  expect(log.scrollTop).toBe(200);
  await user.click(screen.getByRole("button", { name: "Follow" }));
  expect(log.scrollTop).toBe(900);
  expect(screen.queryByRole("button", { name: "Follow" })).not.toBeInTheDocument();
});
