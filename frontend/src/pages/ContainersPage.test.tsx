import { screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import type { components } from "@/api/schema";
import { container } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

function answer(groups: components["schemas"]["GroupOut"][]) {
  server.use(http.get("*/api/containers", () => HttpResponse.json(groups)));
}

test("groups show in API order with their containers", async () => {
  answer([
    { project: "media", label: "media", containers: [container({ name: "plex" }), container({ name: "sonarr" })] },
    { project: null, label: "Other", containers: [container({ name: "adhoc" })] },
  ]);
  renderRoute("/");

  const groups = await screen.findAllByRole("region");
  expect(groups.map((group) => within(group).getByRole("heading").textContent)).toEqual(["media", "Other"]);
  const media = screen.getByRole("region", { name: "media" });
  expect(within(media).getAllByRole("link").map((link) => link.textContent)).toEqual(["plex", "sonarr"]);
  expect(within(media).getByRole("link", { name: "plex" })).toHaveAttribute("href", "/containers/plex");
});

test("a row shows the container fields", async () => {
  answer([
    {
      project: "web",
      label: "web",
      containers: [
        container({
          name: "app",
          state: "running",
          health: "unhealthy",
          tag: "2.1.0",
          latest_version: "2.3.0",
          status: "update",
          severity: "critical",
        }),
      ],
    },
  ]);
  renderRoute("/");

  const row = (await screen.findByRole("link", { name: "app" })).closest("tr");
  if (!row) throw new Error("No row");
  const cells = within(row).getAllByRole("cell").map((cell) => cell.textContent);
  expect(cells).toEqual(["app", "running", "unhealthy", "2.1.0", "2.3.0", "update", "critical"]);
});

test("health none shows no healthcheck, and empty values show a dash", async () => {
  answer([
    {
      project: null,
      label: "Other",
      containers: [container({ name: "db", health: "none", tag: null, latest_version: null, status: "no check" })],
    },
  ]);
  renderRoute("/");

  const row = (await screen.findByRole("link", { name: "db" })).closest("tr");
  if (!row) throw new Error("No row");
  const cells = within(row).getAllByRole("cell").map((cell) => cell.textContent);
  expect(cells).toEqual(["db", "running", "no healthcheck", "-", "-", "no check", ""]);
});

test("the page shows a loading text", async () => {
  server.use(
    http.get("*/api/containers", async () => {
      await delay(50);
      return HttpResponse.json([]);
    }),
  );
  renderRoute("/");

  expect(await screen.findByText("Loading containers…")).toBeInTheDocument();
  expect(await screen.findByText(/No containers/)).toBeInTheDocument();
});

test("no containers shows the empty state", async () => {
  answer([]);
  renderRoute("/");

  expect(await screen.findByText(/No containers/)).toBeInTheDocument();
});

test("an API error shows the error", async () => {
  server.use(
    http.get("*/api/containers", () =>
      HttpResponse.json({ error: "Internal Server Error", detail: "An error occurred. See the WT log." }, { status: 500 }),
    ),
  );
  renderRoute("/");

  expect(await screen.findByRole("alert")).toHaveTextContent("An error occurred. See the WT log.");
});
