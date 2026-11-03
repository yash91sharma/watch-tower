import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Button } from "@/components/ui/button";

test("Button renders a button with its variant", () => {
  render(<Button variant="outline">Save</Button>);

  const button = screen.getByRole("button", { name: "Save" });
  expect(button).toHaveAttribute("data-variant", "outline");
});

test("Button with asChild renders its child element", () => {
  render(
    <Button asChild>
      <a href="/settings">Settings</a>
    </Button>,
  );

  expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("data-slot", "button");
});
