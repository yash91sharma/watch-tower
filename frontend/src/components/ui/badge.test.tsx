import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Badge } from "@/components/ui/badge";

test("Badge renders a span with its variant", () => {
  render(<Badge variant="outline">new</Badge>);

  const badge = screen.getByText("new");
  expect(badge.tagName).toBe("SPAN");
  expect(badge).toHaveAttribute("data-variant", "outline");
});

test("Badge with asChild renders its child element", () => {
  render(
    <Badge asChild>
      <a href="/settings">Settings</a>
    </Badge>,
  );

  expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("data-slot", "badge");
});
