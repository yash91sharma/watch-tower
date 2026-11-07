import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { version } from "../package.json";

import { App } from "@/App";
import { server } from "@/test/server";

test("the app renders the container list at /", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
});

test("a 401 in the app opens the login page", async () => {
  server.use(
    http.get("*/api/containers", () =>
      HttpResponse.json({ error: "Unauthorized", detail: "Log in first" }, { status: 401 }),
    ),
    http.get("*/api/auth/state", () => HttpResponse.json({ setup_required: false, logged_in: false })),
  );

  render(<App />);

  expect(await screen.findByRole("heading", { level: 1, name: "Log in" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/login");
});

test("the footer shows the app version from package.json", async () => {
  render(<App />);

  const footer = await screen.findByRole("contentinfo");
  expect(footer).toHaveTextContent(`WT v${version}`);
});
