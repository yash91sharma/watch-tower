import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FakeEventSource } from "@/test/eventSource";
import { renderRoute } from "@/test/render";

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

  await user.click(screen.getByLabelText("Only matches"));

  await waitFor(() => {
    expect(rows()).toEqual(["get 1", "get 2"]);
  });
});

test("the JSON toggle formats JSON object lines only", async () => {
  const user = await openWithLines(['{"level":"info"}', "plain"]);
  expect(rows()).toEqual(['{"level":"info"}', "plain"]);

  await user.click(screen.getByLabelText("Format JSON"));

  expect(rows()).toEqual(['{\n  "level": "info"\n}', "plain"]);
});
