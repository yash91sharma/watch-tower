import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { FakeEventSource } from "@/test/eventSource";
import { renderRoute } from "@/test/render";

const logStream = () => FakeEventSource.instances.filter((source) => source.url.includes("/logs?")).at(-1);

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
