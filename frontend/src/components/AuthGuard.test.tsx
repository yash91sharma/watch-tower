import { act, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { authStateQuery } from "@/api/queries";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

const states = {
  "setup required": { setup_required: true, logged_in: false },
  "logged out": { setup_required: false, logged_in: false },
  "logged in": { setup_required: false, logged_in: true },
};

test.each([
  ["setup required", "/", "/setup", "Set up Watch Tower"],
  ["setup required", "/login", "/setup", "Set up Watch Tower"],
  ["setup required", "/setup", "/setup", "Set up Watch Tower"],
  ["logged out", "/settings", "/login", "Log in"],
  ["logged out", "/setup", "/login", "Log in"],
  ["logged out", "/login", "/login", "Log in"],
  ["logged in", "/login", "/", "Containers"],
  ["logged in", "/setup", "/", "Containers"],
  ["logged in", "/settings", "/settings", "Settings"],
] as const)("%s: %s opens %s", async (state, from, to, heading) => {
  server.use(http.get("*/api/auth/state", () => HttpResponse.json(states[state])));
  const { router } = renderRoute(from);

  expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe(to);
});

test("the guard shows a loading text until the state comes", async () => {
  renderRoute("/");

  expect(screen.getByText("Loading…")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
});

test("a failed refetch keeps the page", async () => {
  const { queryClient } = renderRoute("/");
  await screen.findByRole("heading", { level: 1, name: "Containers" });
  server.use(http.get("*/api/auth/state", () => HttpResponse.error()));

  await act(async () => {
    await queryClient.refetchQueries({ queryKey: authStateQuery.queryKey });
    // Let React render the new query state.
    await new Promise((resolve) => setTimeout(resolve, 50));
  });

  expect(queryClient.getQueryState(authStateQuery.queryKey)?.status).toBe("error");
  expect(screen.getByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
});

test("an auth state error shows the error page", async () => {
  server.use(
    http.get("*/api/auth/state", () =>
      HttpResponse.json({ error: "Internal Server Error", detail: "Database is locked" }, { status: 500 }),
    ),
  );
  renderRoute("/");

  expect(await screen.findByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
  expect(screen.getByText("Database is locked")).toBeInTheDocument();
});
