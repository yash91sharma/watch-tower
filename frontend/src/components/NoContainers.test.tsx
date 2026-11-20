import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { NoContainers } from "@/components/NoContainers";

test("the text tells which containers WT does not show", () => {
  render(<NoContainers className="text-sm" />);

  const text = screen.getByText(/^No containers\./);
  expect(text).toHaveTextContent(
    "No containers. WT shows all containers on this Docker host, except the containers with the label wt.enable=false.",
  );
  expect(screen.getByText("wt.enable=false").tagName).toBe("CODE");
  expect(text).toHaveClass("text-muted-foreground", "text-sm");
});
