import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { formatTime } from "@/lib/time";
import { FakeEventSource } from "@/test/eventSource";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

const LAST_RUN = "2026-11-02T06:00:00Z";

function status(running: boolean, lastRun: string | null = LAST_RUN) {
  return { running, last_run: lastRun, counts: {} };
}

test("the bar shows the last check time", async () => {
  server.use(http.get("*/api/checks/status", () => HttpResponse.json(status(false))));
  renderRoute("/");

  expect(await screen.findByText(`Last check: ${formatTime(LAST_RUN)}`)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Check now" })).toBeEnabled();
});

test("with no check yet, the bar shows never", async () => {
  server.use(http.get("*/api/checks/status", () => HttpResponse.json(status(false, null))));
  renderRoute("/");

  expect(await screen.findByText("Last check: never")).toBeInTheDocument();
});

test("the button is off during a run", async () => {
  server.use(http.get("*/api/checks/status", () => HttpResponse.json(status(true))));
  renderRoute("/");

  expect(await screen.findByText("Checking…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Check now" })).toBeDisabled();
});

test("Check now starts a run. The end of the run turns the button on", async () => {
  let running = false;
  server.use(
    http.get("*/api/checks/status", () => HttpResponse.json(status(running))),
    http.post("*/api/checks", () => {
      running = true;
      return HttpResponse.json(status(true), { status: 202 });
    }),
  );
  const user = userEvent.setup();
  renderRoute("/");
  await screen.findByText(`Last check: ${formatTime(LAST_RUN)}`);

  await user.click(screen.getByRole("button", { name: "Check now" }));

  expect(await screen.findByText("Checking…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Check now" })).toBeDisabled();

  running = false;
  act(() => {
    FakeEventSource.last.emit("check", { running: false });
  });
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Check now" })).toBeEnabled();
  });
});

test("a failed start shows the error", async () => {
  server.use(
    http.get("*/api/checks/status", () => HttpResponse.json(status(false))),
    http.post("*/api/checks", () =>
      HttpResponse.json({ error: "Conflict", detail: "A check is running" }, { status: 409 }),
    ),
  );
  const user = userEvent.setup();
  renderRoute("/");

  await user.click(await screen.findByRole("button", { name: "Check now" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("A check is running");
});

test("the Check now button of an app checks only that app", async () => {
  let group: string | null = null;
  server.use(
    http.get("*/api/checks/status", () => HttpResponse.json(status(false))),
    http.get("*/api/containers", () =>
      HttpResponse.json([{ project: "media", label: "media", update: "none", containers: [] }]),
    ),
    http.post("*/api/checks", ({ request }) => {
      group = new URL(request.url).searchParams.get("group");
      return HttpResponse.json(status(true), { status: 202 });
    }),
  );
  const user = userEvent.setup();
  renderRoute("/");

  await user.click(await screen.findByRole("button", { name: "Check now: media" }));

  await waitFor(() => {
    expect(group).toBe("media");
  });
  expect(await screen.findByText("Checking…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Check now: media" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Check now" })).toBeDisabled();
});
