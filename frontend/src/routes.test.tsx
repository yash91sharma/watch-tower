import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

test.each([
  ["/", "Containers"],
  ["/containers/web", "web"],
  ["/containers/web/logs", "Logs: web"],
  ["/settings", "Settings"],
])("route %s renders its page in the layout", async (path, heading) => {
  renderRoute(path);

  expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  expect(screen.getByRole("navigation")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Containers" })).toHaveAttribute("href", "/");
  expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
});

test.each([
  ["/setup", "Set up Watch Tower", { setup_required: true, logged_in: false }],
  ["/login", "Log in", { setup_required: false, logged_in: false }],
])("route %s renders with no nav", async (path, heading, state) => {
  server.use(http.get("*/api/auth/state", () => HttpResponse.json(state)));
  renderRoute(path);

  expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
});

test("an unknown path shows the not-found page", async () => {
  renderRoute("/no/such/page");

  expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the container list" })).toHaveAttribute("href", "/");
});

test("the nav marks the link of the open page", async () => {
  renderRoute("/settings");

  expect(await screen.findByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Containers" })).not.toHaveAttribute("aria-current");
});

test("a click on the logo opens the container list", async () => {
  const user = userEvent.setup();
  const { router } = renderRoute("/settings");

  await user.click(await screen.findByRole("link", { name: "WT" }));

  expect(router.state.location.pathname).toBe("/");
  expect(await screen.findByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
});