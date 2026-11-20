import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { containerUsage, groupUsage, history, overview } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

test("the page shows the VM values and the counts from the API", async () => {
  renderRoute("/");

  const vm = await screen.findByRole("region", { name: "Docker VM" });
  expect(within(vm).getByText("25% (2.8 cores)")).toBeInTheDocument();
  expect(within(vm).getByText("3.2 / 8.0 GiB")).toBeInTheDocument();
  expect(within(vm).getByText("Containers: 2.1 GiB")).toBeInTheDocument();
  expect(within(vm).getByText("0.2 / 4.0 GiB")).toBeInTheDocument();
  expect(within(vm).getByText("217.0 / 461.0 GiB")).toBeInTheDocument();
  expect(within(vm).getByText("Read 12.0 KiB/s, write 48.0 KiB/s")).toBeInTheDocument();
  expect(within(vm).getByText("In 1.2 KiB/s, out 300 B/s")).toBeInTheDocument();
  expect(within(vm).getByText("0.52 / 0.40 / 0.35")).toBeInTheDocument();
  expect(within(vm).getByText("3 d 4 h")).toBeInTheDocument();
  expect(within(vm).getByRole("meter", { name: "CPU" })).toHaveAttribute("aria-valuenow", "25");
  expect(screen.getByRole("link", { name: "1 app" })).toHaveAttribute("href", "/apps");
  expect(screen.getByRole("link", { name: "1 running of 1 containers" })).toHaveAttribute("href", "/apps");
});

test("the VM charts use the shared range", async () => {
  const user = userEvent.setup();
  const ranges: string[] = [];
  server.use(
    http.get("*/api/metrics/vm/history", ({ request }) => {
      const range = new URL(request.url).searchParams.get("range") ?? "";
      ranges.push(range);
      return HttpResponse.json(history({ range: range as "1h" }));
    }),
  );
  renderRoute("/");

  const select = await screen.findByRole("combobox", { name: "Range" });
  await user.selectOptions(select, "24 hours");

  expect(await screen.findByRole("heading", { name: "CPU" })).toBeInTheDocument();
  expect(ranges).toEqual(["1h", "24h"]);
});

test("the app list links to the containers and to the groups on App details", async () => {
  server.use(
    http.get("*/api/metrics/overview", () =>
      HttpResponse.json(
        overview({
          groups: [
            groupUsage(),
            groupUsage({
              project: null,
              label: "Other",
              containers: [containerUsage({ name: "tool", state: "exited", cpu_label: "-", mem_label: "-" })],
            }),
          ],
        }),
      ),
    ),
  );
  renderRoute("/");

  const apps = await screen.findByRole("region", { name: "Apps" });
  expect(within(apps).getByRole("link", { name: "site" })).toHaveAttribute("href", "/apps?group=site");
  expect(within(apps).getByRole("link", { name: "web" })).toHaveAttribute("href", "/containers/web");
  expect(within(apps).getByRole("link", { name: "Other" })).toHaveAttribute("href", "/apps?group=Other");
  const tool = within(apps).getByRole("link", { name: "tool" }).closest("tr");
  if (!tool) throw new Error("no row");
  expect(within(tool).getByText("exited")).toBeInTheDocument();
  expect(await within(apps).findByRole("img", { name: "CPU of site, last hour" })).toBeInTheDocument();
  expect(within(apps).getByRole("img", { name: "Memory of web, last hour" })).toBeInTheDocument();
});

test("before the first poll the page says that there are no VM values", async () => {
  server.use(http.get("*/api/metrics/overview", () => HttpResponse.json(overview({ vm: null }))));
  renderRoute("/");

  expect(await screen.findByText("No VM values yet. WT gets them at the next poll.")).toBeInTheDocument();
});

test("with no containers the page shows the empty text", async () => {
  server.use(http.get("*/api/metrics/overview", () => HttpResponse.json(overview({ groups: [] }))));
  renderRoute("/");

  expect(await screen.findByText(/No containers\./)).toBeInTheDocument();
});

test("the page shows the error of the API", async () => {
  server.use(
    http.get("*/api/metrics/overview", () =>
      HttpResponse.json({ error: "Internal Server Error", detail: "An error occurred. See the WT log." }, { status: 500 }),
    ),
  );
  renderRoute("/");

  expect(await screen.findByRole("alert")).toHaveTextContent("An error occurred. See the WT log.");
});
