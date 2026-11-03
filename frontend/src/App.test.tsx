import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App } from "@/App";

test("the app renders the container list at /", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
});
