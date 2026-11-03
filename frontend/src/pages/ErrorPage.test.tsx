import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { expect, test } from "vitest";

import { ErrorPage } from "@/pages/ErrorPage";

function Broken(): never {
  throw new Error("Render failed");
}

test("a render error shows the error page with the message", async () => {
  const router = createMemoryRouter([{ path: "/", element: <Broken />, errorElement: <ErrorPage /> }]);

  render(<RouterProvider router={router} />);

  expect(await screen.findByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
  expect(screen.getByText("Render failed")).toBeInTheDocument();
});
