import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import type { ContainerDetail } from "@/api/types";
import { containerDetail } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

function answer(detail: ContainerDetail) {
  server.use(http.get("*/api/containers/:name", () => HttpResponse.json(detail)));
}

async function block() {
  return within(await screen.findByRole("region", { name: "Update" }));
}

test("the block shows the versions, the severity, the summary and the notes", async () => {
  answer(
    containerDetail({
      status: "update",
      update: {
        from_version: "1.2.0",
        to_version: "1.4.0",
        severity: "critical",
        summary: "Fixes CVE-2026-1.",
        release_notes: "## 1.4.0\n- Fix CVE-2026-1\n\n## 1.3.0\n- New UI",
      },
    }),
  );
  renderRoute("/containers/web");

  const update = await block();
  expect(update.getByText("1.2.0")).toBeInTheDocument();
  expect(update.getByText("1.4.0")).toBeInTheDocument();
  expect(update.getByText("critical")).toBeInTheDocument();
  expect(update.getByText("Fixes CVE-2026-1.")).toBeInTheDocument();
  expect(update.getByTestId("release-notes").textContent).toBe("## 1.4.0\n- Fix CVE-2026-1\n\n## 1.3.0\n- New UI");
});

test("release notes show as plain text, not as HTML", async () => {
  answer(
    containerDetail({
      status: "update",
      update: {
        from_version: "1.0.0",
        to_version: "1.1.0",
        severity: "normal",
        summary: "",
        release_notes: '<img src=x onerror="alert(1)"><b>bold</b>',
      },
    }),
  );
  renderRoute("/containers/web");

  const notes = (await block()).getByTestId("release-notes");
  expect(notes.textContent).toBe('<img src=x onerror="alert(1)"><b>bold</b>');
  expect(notes.querySelector("img, b")).toBeNull();
});

test("with no update, the block shows the status", async () => {
  answer(containerDetail({ status: "up to date", update: null }));
  renderRoute("/containers/web");

  expect((await block()).getByText("No update. Status: up to date.")).toBeInTheDocument();
});

test("status update with no update row says that the next check gets the notes", async () => {
  // For example after a release source change: the repo is known, the notes are not made yet.
  answer(containerDetail({ status: "update", update: null }));
  renderRoute("/containers/web");

  expect(
    (await block()).getByText("A new version is available. The next check gets the release notes."),
  ).toBeInTheDocument();
});
