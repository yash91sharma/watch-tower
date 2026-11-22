import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { AuthCard } from "@/components/AuthCard";

test("the card shows the logo, the product name, the title and the form", () => {
  const { container } = render(
    <AuthCard title="Log in">
      <p>The form</p>
    </AuthCard>,
  );

  expect(screen.getByRole("main")).toHaveClass("min-h-svh", "items-center");
  expect(container.querySelector("svg.wt-logo")).not.toBeNull();
  expect(screen.getByText("Watch Tower")).toBeInTheDocument();
  const title = screen.getByRole("heading", { level: 1, name: "Log in" });
  // The title and the form are in one card.
  expect(title.parentElement).toHaveClass("rounded-xl", "border", "bg-card");
  expect(title.parentElement).toContainElement(screen.getByText("The form"));
});
