import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App } from "@/App";

test("the app renders the home page", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "Watch Tower" })).toBeInTheDocument();
});
