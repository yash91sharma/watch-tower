import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

test("a click on the group name collapses and expands the group", async () => {
  const user = userEvent.setup();
  answer([{ project: "media", label: "media", containers: [container({ name: "plex" }), container({ name: "sonarr" })] }]);
  renderRoute("/");

  const toggle = await screen.findByRole("button", { name: "media" });
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("2 containers")).toBeInTheDocument();

  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("link", { name: "plex" })).not.toBeInTheDocument();
  expect(screen.getByText("2 containers")).toBeInTheDocument();

  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "plex" })).toBeInTheDocument();
});

test("a collapsed group stays collapsed when the page opens again", async () => {
  const user = userEvent.setup();
  answer([
    { project: "media", label: "media", containers: [container({ name: "plex" })] },
    { project: null, label: "Other", containers: [container({ name: "adhoc" })] },
  ]);
  const first = renderRoute("/");
  await user.click(await screen.findByRole("button", { name: "media" }));
  first.unmount();

  renderRoute("/");

  expect(await screen.findByRole("button", { name: "media" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "Other" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.queryByRole("link", { name: "plex" })).not.toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "media" })).getByText("1 container")).toBeInTheDocument();
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
  expect(cells).toEqual(["app", "running", "unhealthy", "2.1.0", "2.3.0", "update available", "critical"]);
  expect(within(row).getByText("update available")).toHaveAttribute("data-variant", "info");
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

test("the table has clear column names", async () => {
  answer([{ project: "web", label: "web", containers: [container({ name: "app" })] }]);
  renderRoute("/");

  const region = await screen.findByRole("region", { name: "web" });
  expect(within(region).getAllByRole("columnheader").map((head) => head.textContent)).toEqual([
    "Name",
    "State",
    "Health",
    "Current version",
    "Latest version",
    "Version status",
    "Update severity",
  ]);
});

test("every second row has a stripe color", async () => {
  answer([
    {
      project: "web",
      label: "web",
      containers: [container({ name: "a" }), container({ name: "b" }), container({ name: "c" })],
    },
  ]);
  renderRoute("/");

  const rows = await Promise.all(["a", "b", "c"].map(async (name) => (await screen.findByRole("link", { name })).closest("tr")));
  expect(rows.map((row) => row?.classList.contains("even:bg-muted/30"))).toEqual([true, true, true]);
});
