import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import type { components } from "@/api/schema";
import { formatTime } from "@/lib/time";
import { containerDetail } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

function answer(detail: components["schemas"]["ContainerDetail"]) {
  server.use(http.get("*/api/containers/:name", () => HttpResponse.json(detail)));
}

test("the page shows the state, the health and the link to the logs", async () => {
  answer(containerDetail({ name: "web", state: "restarting", health: "unhealthy" }));
  renderRoute("/containers/web");

  expect(await screen.findByRole("heading", { level: 1, name: "web" })).toBeInTheDocument();
  expect(await screen.findByText("restarting")).toBeInTheDocument();
  expect(screen.getByText("unhealthy")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Logs" })).toHaveAttribute("href", "/containers/web/logs");
});

test("the page shows the events of the last 7 days, newest first", async () => {
  const unhealthy = "2026-11-01T10:00:00Z";
  const recovered = "2026-11-01T10:05:00Z";
  answer(
    containerDetail({
      events: [
        { kind: "recovered_health", time: recovered },
        { kind: "became_unhealthy", time: unhealthy },
      ],
    }),
  );
  renderRoute("/containers/web");

  const events = within(await screen.findByRole("region", { name: "Events (last 7 days)" }));
  const items = events.getAllByRole("listitem").map((item) => item.textContent);
  expect(items).toEqual([`${formatTime(recovered)}: Healthy again`, `${formatTime(unhealthy)}: Unhealthy`]);
});

test("with no events, the page says so", async () => {
  answer(containerDetail());
  renderRoute("/containers/web");

  expect(await screen.findByText("No events in the last 7 days.")).toBeInTheDocument();
});

test("an unknown container shows the API error", async () => {
  server.use(
    http.get("*/api/containers/:name", () =>
      HttpResponse.json({ error: "Not Found", detail: "No container 'web'" }, { status: 404 }),
    ),
  );
  renderRoute("/containers/web");

  expect(await screen.findByRole("alert")).toHaveTextContent("No container 'web'");
});

test("no image and no tag show a dash", async () => {
  answer(containerDetail({ image: null, tag: null }));
  renderRoute("/containers/web");

  const image = (await screen.findByText("Image")).nextElementSibling;
  const running = screen.getByText("Running").nextElementSibling;
  expect(image).toHaveTextContent("-");
  expect(running).toHaveTextContent("-");
});

test("the breadcrumb links to the container list", async () => {
  answer(containerDetail({ name: "web" }));
  renderRoute("/containers/web");
  const crumbs = await screen.findByRole("navigation", { name: "Breadcrumb" });

  expect(within(crumbs).getByRole("link", { name: "Containers" })).toHaveAttribute("href", "/");
  expect(within(crumbs).getByText("web")).toHaveAttribute("aria-current", "page");
});
