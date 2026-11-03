// Accessibility: each control on each page has a name (a label, text or aria-label).
// Axe in the E2E tests (16.18) checks contrast and the rest in a real browser.
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { container, containerDetail } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

const ROLES = ["button", "link", "textbox", "searchbox", "checkbox", "combobox", "spinbutton"] as const;

function expectNamedControls() {
  for (const role of ROLES) {
    const all = screen.queryAllByRole(role);
    const named = screen.queryAllByRole(role, { name: /\S/ });
    expect(named, `each ${role} has a name`).toHaveLength(all.length);
  }
}

test.each([
  ["/", "Containers"],
  ["/containers/web", "web"],
  ["/containers/web/logs", "Logs: web"],
  ["/settings", "Settings"],
])("all controls on %s have a name", async (path, heading) => {
  server.use(
    http.get("*/api/containers", () =>
      HttpResponse.json([{ project: null, label: "Other", containers: [container()] }]),
    ),
    http.get("*/api/containers/:name", () =>
      HttpResponse.json(
        containerDetail({
          source_confirmed: false,
          update: { from_version: "1", to_version: "2", severity: "normal", summary: "", release_notes: "" },
        }),
      ),
    ),
  );
  renderRoute(path);
  await screen.findByRole("heading", { level: 1, name: heading });
  await screen.findAllByRole("button");

  expectNamedControls();
});

test.each([
  ["/login", { setup_required: false, logged_in: false }, "Log in"],
  ["/setup", { setup_required: true, logged_in: false }, "Set up Watch Tower"],
])("all controls on %s have a name", async (path, state, heading) => {
  server.use(http.get("*/api/auth/state", () => HttpResponse.json(state)));
  renderRoute(path);
  await screen.findByRole("heading", { level: 1, name: heading });

  expectNamedControls();
});
