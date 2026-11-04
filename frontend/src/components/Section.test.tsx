import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Section } from "@/components/Section";

test("Section is a region with its title as the heading and the name", () => {
  render(
    <Section title="Update">
      <p>Body</p>
    </Section>,
  );

  const region = screen.getByRole("region", { name: "Update" });
  expect(region).toContainElement(screen.getByRole("heading", { level: 2, name: "Update" }));
  expect(region).toContainElement(screen.getByText("Body"));
});
