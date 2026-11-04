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

test("a thrown value that is not an Error shows 'Unknown error'", async () => {
  function BrokenWithText(): never {
    // eslint-disable-next-line @typescript-eslint/only-throw-error
    throw "not an Error";
  }
  const router = createMemoryRouter([{ path: "/", element: <BrokenWithText />, errorElement: <ErrorPage /> }]);

  render(<RouterProvider router={router} />);

  expect(await screen.findByText("Unknown error")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the container list" })).toHaveAttribute("href", "/");
});
