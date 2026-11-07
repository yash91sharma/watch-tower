import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test } from "vitest";

import { container } from "@/test/fixtures";
import { setDesktop } from "@/test/media";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

beforeEach(() => {
  server.use(
    http.get("*/api/containers", () =>
      HttpResponse.json([
        { project: "media", label: "media", update: "none", containers: [container({ name: "plex" }), container({ name: "sonarr" })] },
        { project: null, label: "Other", update: "none", containers: [container({ name: "adhoc" })] },
      ]),
    ),
  );
});

const sidebar = () => screen.findByRole("navigation", { name: "Container list" });
const toggle = () => screen.getByRole("button", { name: "Sidebar" });

test("on a large screen the sidebar shows the groups and their containers", async () => {
  setDesktop(true);
  renderRoute("/settings");
  const nav = await sidebar();

  expect(await within(nav).findByText("media")).toBeInTheDocument();
  expect(within(nav).getByText("Other")).toBeInTheDocument();
  const links = within(nav).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual(["plex", "sonarr", "adhoc"]);
  expect(within(nav).getByRole("link", { name: "plex" })).toHaveAttribute("href", "/containers/plex");
  expect(toggle()).toHaveAttribute("aria-expanded", "true");
});

test("the open container is marked and has links to its details and logs", async () => {
  setDesktop(true);
  renderRoute("/containers/plex/logs");
  const nav = await sidebar();

  const plex = await within(nav).findByRole("link", { name: "plex" });
  expect(plex).toHaveClass("font-semibold");
  expect(within(nav).getByRole("link", { name: "Details" })).toHaveAttribute("href", "/containers/plex");
  expect(within(nav).getByRole("link", { name: "Logs" })).toHaveAttribute("aria-current", "page");
  expect(within(nav).getAllByRole("link", { name: "Details" })).toHaveLength(1);
});

test("on a large screen the browser keeps the choice of the admin", async () => {
  setDesktop(true);
  const user = userEvent.setup();
  const { unmount } = renderRoute("/settings");
  await sidebar();

  await user.click(toggle());
  expect(screen.queryByRole("navigation", { name: "Container list" })).not.toBeInTheDocument();
  expect(toggle()).toHaveAttribute("aria-expanded", "false");
  unmount();

  renderRoute("/settings");
  await screen.findByRole("heading", { level: 1, name: "Settings" });
  expect(screen.queryByRole("navigation", { name: "Container list" })).not.toBeInTheDocument();

  await user.click(toggle());
  expect(await sidebar()).toBeInTheDocument();
  expect(localStorage.getItem("wt.sidebar")).toBe("open");
});

test("on a small screen the sidebar opens with the button and closes when a page opens", async () => {
  const user = userEvent.setup();
  const { router } = renderRoute("/settings");
  await screen.findByRole("heading", { level: 1, name: "Settings" });
  expect(screen.queryByRole("navigation", { name: "Container list" })).not.toBeInTheDocument();

  await user.click(toggle());
  await user.click(await within(await sidebar()).findByRole("link", { name: "sonarr" }));

  expect(router.state.location.pathname).toBe("/containers/sonarr");
  expect(screen.queryByRole("navigation", { name: "Container list" })).not.toBeInTheDocument();
  expect(localStorage.length).toBe(0);
});

test("the sidebar tells the admin when there are no containers", async () => {
  setDesktop(true);
  server.use(http.get("*/api/containers", () => HttpResponse.json([])));
  renderRoute("/settings");

  expect(await within(await sidebar()).findByText("No containers.")).toBeInTheDocument();
});

test("on a large screen the sidebar stays open when a page opens", async () => {
  setDesktop(true);
  const user = userEvent.setup();
  const { router } = renderRoute("/settings");

  await user.click(await within(await sidebar()).findByRole("link", { name: "adhoc" }));

  expect(router.state.location.pathname).toBe("/containers/adhoc");
  expect(await sidebar()).toBeInTheDocument();
});
