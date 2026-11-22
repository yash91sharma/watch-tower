import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FakeEventSource } from "@/test/eventSource";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

const logStream = () => FakeEventSource.instances.filter((source) => source.url.includes("/logs?")).at(-1);

// jsdom has no layout. TanStack Virtual needs sizes to show rows, and scrollTo.
beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(20);
  Element.prototype.scrollTo = vi.fn();
});
afterEach(() => {
  vi.restoreAllMocks();
});

/** Open the logs page and send the lines. */
async function openWithLines(texts: string[]) {
  const user = userEvent.setup();
  renderRoute("/containers/web/logs");
  await screen.findByRole("heading", { level: 1, name: "Logs: web" });
  act(() => {
    for (const text of texts) logStream()?.emit("message", { time: null, stream: "stdout", text });
  });
  await screen.findByText(texts.at(-1) ?? "");
  return user;
}

const rows = () => Array.from(screen.getByRole("log").querySelectorAll("[data-index]"), (row) => row.textContent);

test("the page reads the log with the tail size from the select", async () => {
  const user = userEvent.setup();
  renderRoute("/containers/web/logs");
  await screen.findByRole("heading", { level: 1, name: "Logs: web" });
  expect(logStream()?.url).toBe("/api/containers/web/logs?tail=500");

  await user.selectOptions(screen.getByLabelText("Tail"), "5000");

  expect(logStream()?.url).toBe("/api/containers/web/logs?tail=5000");
});

test("the page shows a stream error", async () => {
  renderRoute("/containers/web/logs");
  await screen.findByRole("heading", { level: 1, name: "Logs: web" });

  act(() => {
    logStream()?.emit("error", "Docker is not connected");
  });

  expect(screen.getByRole("alert")).toHaveTextContent("Docker is not connected");
});

test("an unknown container shows the API error, not the stream error", async () => {
  server.use(
    http.get("*/api/containers/:name", () =>
      HttpResponse.json({ error: "Not Found", detail: "No container 'web'" }, { status: 404 }),
    ),
  );
  renderRoute("/containers/web/logs");
  await screen.findByRole("heading", { level: 1, name: "Logs: web" });

  act(() => {
    logStream()?.fail();
  });

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent("No container 'web'");
  });
  expect(screen.getAllByRole("alert")).toHaveLength(1);
});

test("search highlights the matches and gives the count, not case-sensitive", async () => {
  const user = await openWithLines(["GET /a", "post /b", "get /c"]);

  await user.type(screen.getByLabelText("Search"), "get");

  expect(screen.getByText("1 of 2")).toBeInTheDocument();
  const marks = within(screen.getByRole("log"))
    .getAllByText(/get/i, { selector: "mark" })
    .map((mark) => mark.textContent);
  expect(marks).toEqual(["GET", "get"]);
});

test("next and previous go through the matches", async () => {
  const user = await openWithLines(["get 1", "x", "get 2"]);
  await user.type(screen.getByLabelText("Search"), "get");

  await user.click(screen.getByRole("button", { name: "Next match" }));
  expect(screen.getByText("2 of 2")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next match" }));
  expect(screen.getByText("1 of 2")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Previous match" }));
  expect(screen.getByText("2 of 2")).toBeInTheDocument();
});

test("no match says so", async () => {
  const user = await openWithLines(["a", "b"]);

  await user.type(screen.getByLabelText("Search"), "zzz");

  expect(screen.getByText("No match")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next match" })).toBeDisabled();
});

test("only matches shows only the lines with a match", async () => {
  const user = await openWithLines(["get 1", "x", "get 2"]);
  await user.type(screen.getByLabelText("Search"), "get");

  const only = screen.getByRole("button", { name: "Only matches" });
  expect(only).toHaveAttribute("aria-pressed", "false");
  await user.click(only);
  expect(only).toHaveAttribute("aria-pressed", "true");

  await waitFor(() => {
    expect(rows()).toEqual(["get 1", "get 2"]);
  });
});

test("the JSON toggle formats JSON object lines only", async () => {
  const user = await openWithLines(['{"level":"info"}', "plain"]);
  expect(rows()).toEqual(['{"level":"info"}', "plain"]);

  await user.click(screen.getByRole("button", { name: "Format JSON" }));

  expect(rows()).toEqual(['{\n  "level": "info"\n}', "plain"]);
});

test("the download link opens logs.txt", async () => {
  renderRoute("/containers/my app/logs");

  const link = await screen.findByRole("link", { name: "Download" });

  expect(link).toHaveAttribute("href", "/api/containers/my%20app/logs.txt");
  expect(link).toHaveAttribute("download");
});

test("the breadcrumb goes back to the container page", async () => {
  const user = userEvent.setup();
  const { router } = renderRoute("/containers/web/logs");
  const crumbs = await screen.findByRole("navigation", { name: "Breadcrumb" });

  expect(within(crumbs).getByRole("link", { name: "Apps" })).toHaveAttribute("href", "/apps");
  expect(within(crumbs).getByText("Logs")).toHaveAttribute("aria-current", "page");
  await user.click(within(crumbs).getByRole("link", { name: "web" }));

  expect(router.state.location.pathname).toBe("/containers/web");
});

test("in the search, Enter goes to the next match, Shift+Enter to the previous match, and Escape clears it", async () => {
  const user = await openWithLines(["get 1", "x", "get 2"]);
  const search = screen.getByLabelText("Search");
  await user.type(search, "get");

  await user.keyboard("{Enter}");
  expect(screen.getByText("2 of 2")).toBeInTheDocument();
  await user.keyboard("{Shift>}{Enter}{/Shift}");
  expect(screen.getByText("1 of 2")).toBeInTheDocument();
  await user.keyboard("{Escape}");
  expect(search).toHaveValue("");
});

test("all log controls are in one toolbar", async () => {
  renderRoute("/containers/web/logs");

  const toolbar = await screen.findByRole("toolbar", { name: "Log controls" });
  for (const name of ["Previous match", "Next match", "Only matches", "Format JSON"]) {
    expect(within(toolbar).getByRole("button", { name })).toBeInTheDocument();
  }
  expect(within(toolbar).getByLabelText("Search")).toBeInTheDocument();
  expect(within(toolbar).getByLabelText("Tail")).toBeInTheDocument();
  expect(within(toolbar).getByRole("link", { name: "Download" })).toBeInTheDocument();
});
