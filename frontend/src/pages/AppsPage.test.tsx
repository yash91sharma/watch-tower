import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";

import type { Group } from "@/api/types";
import { container } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

function answer(groups: Group[]) {
  server.use(http.get("*/api/containers", () => HttpResponse.json(groups)));
}

test("groups show in API order with their containers", async () => {
  answer([
    { project: "media", label: "media", update: "none", containers: [container({ name: "plex" }), container({ name: "sonarr" })] },
    { project: null, label: "Other", update: "none", containers: [container({ name: "adhoc" })] },
  ]);
  renderRoute("/apps");

  const groups = await screen.findAllByRole("region");
  expect(groups.map((group) => within(group).getByRole("heading").textContent)).toEqual(["media", "Other"]);
  const media = screen.getByRole("region", { name: "media" });
  const names = within(media)
    .getAllByRole("link")
    .filter((link) => !link.hasAttribute("target") && !link.getAttribute("href")?.endsWith("/logs"));
  expect(names.map((link) => link.textContent)).toEqual(["plex", "sonarr"]);
  expect(within(media).getByRole("link", { name: "plex" })).toHaveAttribute("href", "/containers/plex");
});

test("a click on the group name collapses and expands the group", async () => {
  const user = userEvent.setup();
  answer([{ project: "media", label: "media", update: "none", containers: [container({ name: "plex" }), container({ name: "sonarr" })] }]);
  renderRoute("/apps");

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
    { project: "media", label: "media", update: "none", containers: [container({ name: "plex" })] },
    { project: null, label: "Other", update: "none", containers: [container({ name: "adhoc" })] },
  ]);
  const first = renderRoute("/apps");
  await user.click(await screen.findByRole("button", { name: "media" }));
  first.unmount();

  renderRoute("/apps");

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
      update: "none",
      containers: [
        container({
          name: "app",
          state: "running",
          health: "unhealthy",
          health_label: "unhealthy",
          tag: "2.1.0",
          latest_version: "2.3.0",
          status: "update",
          status_label: "update available",
          severity: "critical",
        }),
      ],
    },
  ]);
  renderRoute("/apps");

  const row = (await screen.findByRole("link", { name: "app" })).closest("tr");
  if (!row) throw new Error("No row");
  const cells = within(row).getAllByRole("cell").map((cell) => cell.textContent);
  // The overview has no values for "app": CPU and memory show "-".
  // The update status and the severity are in one column.
  expect(cells).toEqual(["app", "running", "unhealthy", "-", "-", "2.1.0", "2.3.0", "update availablecritical"]);
  expect(within(row).getByText("update available")).toHaveAttribute("data-variant", "info");
});

test("the row shows the labels from the API, and empty values show a dash", async () => {
  answer([
    {
      project: null,
      label: "Other",
      update: "none",
      containers: [container({
          name: "db",
          health: "none",
          health_label: "no healthcheck",
          tag: null,
          latest_version: null,
          latest_url: null,
          status: "no check",
          status_label: "no check",
        }),
      ],
    },
  ]);
  renderRoute("/apps");

  const row = (await screen.findByRole("link", { name: "db" })).closest("tr");
  if (!row) throw new Error("No row");
  const cells = within(row).getAllByRole("cell").map((cell) => cell.textContent);
  expect(cells).toEqual(["db", "running", "no healthcheck", "-", "-", "-", "-", "no check"]);
});

test("the page shows a loading text", async () => {
  server.use(
    http.get("*/api/containers", async () => {
      await delay(50);
      return HttpResponse.json([]);
    }),
  );
  renderRoute("/apps");

  expect(await screen.findByText("Loading containers…")).toBeInTheDocument();
  expect(await screen.findByText(/No containers/)).toBeInTheDocument();
});

test("no containers shows the empty state", async () => {
  answer([]);
  renderRoute("/apps");

  expect(await screen.findByText(/No containers/)).toBeInTheDocument();
});

test("an API error shows the error", async () => {
  server.use(
    http.get("*/api/containers", () =>
      HttpResponse.json({ error: "Internal Server Error", detail: "An error occurred. See the WT log." }, { status: 500 }),
    ),
  );
  renderRoute("/apps");

  expect(await screen.findByRole("alert")).toHaveTextContent("An error occurred. See the WT log.");
});

test("the table has clear column names", async () => {
  answer([{ project: "web", label: "web", update: "none", containers: [container({ name: "app" })] }]);
  renderRoute("/apps");

  const region = await screen.findByRole("region", { name: "web" });
  expect(within(region).getAllByRole("columnheader").map((head) => head.textContent)).toEqual([
    "Name",
    "State",
    "Health",
    "CPU",
    "Memory",
    "Current version",
    "Latest version",
    "Update",
  ]);
});

test("on a phone, the table shows only the name, the health and the update", async () => {
  answer([{ project: "web", label: "web", update: "none", containers: [container({ name: "app" })] }]);
  renderRoute("/apps");

  const region = await screen.findByRole("region", { name: "web" });
  // jsdom has no CSS: the max-sm:hidden class hides a column below the sm width.
  const shown = (cells: HTMLElement[]) =>
    cells.filter((cell) => !cell.classList.contains("max-sm:hidden")).map((cell) => cell.textContent);
  expect(shown(within(region).getAllByRole("columnheader"))).toEqual(["Name", "Health", "Update"]);
  expect(shown(within(region).getAllByRole("cell"))).toHaveLength(3);
  // A long name wraps, and the group header wraps (the Check now button stays in the box).
  const name = within(region).getByRole("link", { name: "app" });
  expect(name).toHaveClass("max-sm:break-all");
  // The table cells do not wrap (whitespace-nowrap). The name cell must, on a phone.
  expect(name.closest("td")).toHaveClass("max-sm:whitespace-normal");
  expect(within(region).getByRole("heading", { name: "web" }).parentElement).toHaveClass("flex-wrap");
});

test("every second row has a stripe color", async () => {
  answer([
    {
      project: "web",
      label: "web",
      update: "none",
      containers: [container({ name: "a" }), container({ name: "b" }), container({ name: "c" })],
    },
  ]);
  renderRoute("/apps");

  const rows = await Promise.all(["a", "b", "c"].map(async (name) => (await screen.findByRole("link", { name })).closest("tr")));
  expect(rows.map((row) => row?.classList.contains("even:bg-muted/30"))).toEqual([true, true, true]);
});

test("the group header color shows the update level of the group", async () => {
  answer([
    { project: "a", label: "a", update: "critical", containers: [container({ name: "a1" })] },
    { project: "b", label: "b", update: "update", containers: [container({ name: "b1" })] },
    { project: "c", label: "c", update: "none", containers: [container({ name: "c1" })] },
  ]);
  renderRoute("/apps");

  const header = (label: string) => screen.getByRole("heading", { name: label }).parentElement;
  await screen.findByRole("heading", { name: "a" });
  expect(header("a")).toHaveClass("bg-group-critical");
  expect(header("b")).toHaveClass("bg-group-update");
  expect(header("c")).toHaveClass("bg-group-ok");
});

test("the latest version links to its GitHub release in a new tab", async () => {
  answer([
    {
      project: "web",
      label: "web",
      update: "none",
      containers: [container({ name: "a" }), container({ name: "b", latest_version: null, latest_url: null })],
    },
  ]);
  renderRoute("/apps");

  const link = await screen.findByRole("link", { name: "1.27.0" });
  expect(link).toHaveAttribute("href", "https://github.com/nginx/nginx/releases/tag/1.27.0");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noreferrer");
  expect(screen.getAllByRole("link", { name: "1.27.0" })).toHaveLength(1);
});

test("the table links always have an underline, and the release link has an external-link icon", async () => {
  answer([{ project: "web", label: "web", update: "none", containers: [container({ name: "a" })] }]);
  renderRoute("/apps");

  const release = await screen.findByRole("link", { name: "1.27.0" });
  expect(release).toHaveClass("underline");
  expect(release.querySelector("svg")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "a" })).toHaveClass("underline");
});

test("a row shows the CPU and memory of the container with a sparkline", async () => {
  answer([{ project: "site", label: "site", update: "none", containers: [container({ name: "web" })] }]);
  renderRoute("/apps");

  const site = await screen.findByRole("region", { name: "site" });
  // App details shows only the used memory (a narrow column).
  const row = (await within(site).findByText("1.0 GiB")).closest("tr");
  if (!row) throw new Error("no row");
  expect(within(row).getByText("9.1% (1.0 core)")).toBeInTheDocument();
  expect(await within(row).findByRole("img", { name: "CPU of web, last hour" })).toBeInTheDocument();
  expect(within(row).getByRole("img", { name: "Memory of web, last hour" })).toBeInTheDocument();
});

test("the name cell has a Logs link", async () => {
  answer([{ project: "site", label: "site", update: "none", containers: [container({ name: "web" })] }]);
  renderRoute("/apps");

  expect(await screen.findByRole("link", { name: "Logs of web" })).toHaveAttribute("href", "/containers/web/logs");
});

test("the group header shows the sums of the group", async () => {
  answer([{ project: "site", label: "site", update: "none", containers: [container({ name: "web" })] }]);
  renderRoute("/apps");

  const site = await screen.findByRole("region", { name: "site" });
  expect(await within(site).findByText("CPU 9.1% (1.0 core)")).toBeInTheDocument();
  expect(within(site).getByText("Memory 1.0 GiB")).toBeInTheDocument();
});

test("?group= opens that group and scrolls to it", async () => {
  const scroll = vi.fn();
  Element.prototype.scrollIntoView = scroll;
  localStorage.setItem("wt.collapsedGroups", JSON.stringify(["media", "Other"]));
  answer([
    { project: "media", label: "media", update: "none", containers: [container({ name: "plex" })] },
    { project: null, label: "Other", update: "none", containers: [container({ name: "adhoc" })] },
  ]);
  renderRoute("/apps?group=media");

  expect(await screen.findByRole("button", { name: "media" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "Other" })).toHaveAttribute("aria-expanded", "false");
  expect(scroll).toHaveBeenCalledTimes(1);
});

test("Collapse all and Expand all change all groups, and the change stays", async () => {
  const user = userEvent.setup();
  answer([
    { project: "media", label: "media", update: "none", containers: [container({ name: "plex" })] },
    { project: null, label: "Other", update: "none", containers: [container({ name: "adhoc" })] },
  ]);
  const first = renderRoute("/apps");

  await user.click(await screen.findByRole("button", { name: "Collapse all" }));
  expect(screen.getByRole("button", { name: "media" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "Other" })).toHaveAttribute("aria-expanded", "false");
  first.unmount();

  renderRoute("/apps");
  expect(await screen.findByRole("button", { name: "media" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "Other" })).toHaveAttribute("aria-expanded", "false");

  await user.click(screen.getByRole("button", { name: "Expand all" }));
  expect(screen.getByRole("button", { name: "media" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "Other" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "plex" })).toBeInTheDocument();
});

test("with no containers, the page has no Collapse all and Expand all buttons", async () => {
  answer([]);
  renderRoute("/apps");

  expect(await screen.findByText(/no containers/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Collapse all" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Expand all" })).not.toBeInTheDocument();
});
