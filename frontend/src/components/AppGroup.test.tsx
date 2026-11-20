import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { AppGroup } from "@/components/AppGroup";

function group(fields: Partial<Parameters<typeof AppGroup>[0]> = {}) {
  return (
    <AppGroup label="media" count={2} open onToggle={() => undefined} {...fields}>
      <p>Body</p>
    </AppGroup>
  );
}

test("the card is a region with the group name, the count and the body", () => {
  render(group({ actions: <button type="button">Action</button> }));

  const region = screen.getByRole("region", { name: "media" });
  expect(region).toContainElement(screen.getByRole("heading", { level: 2, name: "media" }));
  expect(screen.getByText("2 containers")).toBeInTheDocument();
  expect(screen.getByText("Body")).toBeVisible();
  expect(screen.getByRole("button", { name: "Action" })).toBeInTheDocument();
});

test("the name button collapses the group: the header stays, the body goes", async () => {
  const user = userEvent.setup();
  const onToggle = vi.fn();
  const { rerender } = render(group({ onToggle }));

  await user.click(screen.getByRole("button", { name: "media" }));
  expect(onToggle).toHaveBeenCalledTimes(1);

  rerender(group({ open: false }));
  expect(screen.getByRole("button", { name: "media" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText("Body")).not.toBeVisible();
  expect(screen.getByText("2 containers")).toBeInTheDocument();
});

test("the header shows the sums when the page gives them", () => {
  render(group({ sums: { cpu_label: "9.1% (1.0 core)", mem_label: "1.0 GiB" } }));

  expect(screen.getByText("CPU 9.1% (1.0 core)")).toBeInTheDocument();
  expect(screen.getByText("Memory 1.0 GiB")).toBeInTheDocument();
});

test("the heading level and the update tint come from the page", () => {
  const { rerender } = render(group({ headingLevel: 3 }));
  expect(screen.getByRole("heading", { level: 3, name: "media" })).toBeInTheDocument();
  expect(screen.getByRole("heading").parentElement).not.toHaveClass("bg-group-critical");

  rerender(group({ update: "critical" }));
  expect(screen.getByRole("heading").parentElement).toHaveClass("bg-group-critical");
});

test("focus scrolls the card into view", () => {
  const scroll = vi.fn();
  Element.prototype.scrollIntoView = scroll;
  render(group({ focus: true }));

  expect(scroll).toHaveBeenCalledTimes(1);
});
