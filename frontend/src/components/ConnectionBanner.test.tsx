import { act, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { FakeEventSource } from "@/test/eventSource";
import { renderRoute } from "@/test/render";

const WT_LOST = "Watch Tower is not connected. Trying again…";
const DOCKER_LOST = "Docker is not connected. The data can be old.";

test("the banner shows when WT is not connected, and hides after the reconnect", async () => {
  renderRoute("/");
  await screen.findByRole("heading", { level: 1, name: "Containers" });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();

  act(() => {
    FakeEventSource.last.emit("error");
  });
  expect(screen.getByRole("status")).toHaveTextContent(WT_LOST);

  // The hook connects again after 3 s.
  await screen.findByText(WT_LOST);
  await act(() => new Promise((resolve) => setTimeout(resolve, 3100)));
  act(() => {
    FakeEventSource.last.emit("open");
  });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("the banner shows when Docker is not connected", async () => {
  renderRoute("/");
  await screen.findByRole("heading", { level: 1, name: "Containers" });

  act(() => {
    FakeEventSource.last.emit("docker", { connected: false });
  });
  expect(screen.getByRole("status")).toHaveTextContent(DOCKER_LOST);

  act(() => {
    FakeEventSource.last.emit("docker", { connected: true });
  });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
