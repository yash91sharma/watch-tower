import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { ApiError } from "@/api/client";
import { QueryPending } from "@/components/QueryPending";

test("with no error it shows the loading text", () => {
  render(<QueryPending error={null} text="Loading containers…" />);

  expect(screen.getByText("Loading containers…")).toBeInTheDocument();
});

test("the default loading text is Loading…", () => {
  render(<QueryPending error={null} />);

  expect(screen.getByText("Loading…")).toBeInTheDocument();
});

test("an error shows as an alert, with no loading text", () => {
  render(<QueryPending error={new ApiError(500, "Server error")} />);

  expect(screen.getByRole("alert")).toHaveTextContent("Server error");
  expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
});
