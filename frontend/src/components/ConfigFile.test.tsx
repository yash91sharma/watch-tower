import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test } from "vitest";

import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

const FILE = { format_version: 1, settings: {}, containers: [] };

let calls: { dryRun: string | null; body: unknown }[] = [];

beforeEach(() => {
  calls = [];
  server.use(
    http.post("*/api/config/import", async ({ request }) => {
      const dryRun = new URL(request.url).searchParams.get("dry_run");
      calls.push({ dryRun, body: await request.json() });
      return HttpResponse.json({
        dry_run: dryRun === "true",
        valid: true,
        settings: 8,
        containers_added: 1,
        containers_updated: 2,
        errors: [],
      });
    }),
  );
});

async function upload(text: string) {
  const user = userEvent.setup();
  renderRoute("/settings");
  const section = within(await screen.findByRole("region", { name: "Export and import" }));
  await user.upload(section.getByLabelText("Config file"), new File([text], "wt.json", { type: "application/json" }));
  return { user, section };
}

test("export links to the export file", async () => {
  renderRoute("/settings");

  const link = await screen.findByRole("link", { name: "Export" });

  expect(link).toHaveAttribute("href", "/api/config/export");
  expect(link).toHaveAttribute("download");
});

test("import sends the file to the dry run, shows the counts, then imports on confirm", async () => {
  const { user, section } = await upload(JSON.stringify(FILE));

  expect(await section.findByText("8 settings, 1 new container, 2 changed containers.")).toBeInTheDocument();
  expect(calls).toEqual([{ dryRun: "true", body: FILE }]);

  await user.click(section.getByRole("button", { name: "Import" }));

  expect(await section.findByText("Imported.")).toBeInTheDocument();
  expect(calls[1]).toEqual({ dryRun: "false", body: FILE });
});

test("cancel imports nothing", async () => {
  const { user, section } = await upload(JSON.stringify(FILE));
  await section.findByRole("button", { name: "Import" });

  await user.click(section.getByRole("button", { name: "Cancel" }));

  expect(section.queryByRole("button", { name: "Import" })).not.toBeInTheDocument();
  expect(calls).toHaveLength(1);
});

test("a bad file shows the dry run errors and no Import button", async () => {
  server.use(
    http.post("*/api/config/import", () =>
      HttpResponse.json({
        dry_run: true,
        valid: false,
        settings: 0,
        containers_added: 0,
        containers_updated: 0,
        errors: [{ field: "format_version", message: "Input should be 1" }],
      }),
    ),
  );
  const { section } = await upload(JSON.stringify({ format_version: 2 }));

  expect(await section.findByRole("alert")).toHaveTextContent("format_version: Input should be 1");
  expect(section.queryByRole("button", { name: "Import" })).not.toBeInTheDocument();
});

test("a file that is not JSON shows an error and sends nothing", async () => {
  const { section } = await upload("not json");

  expect(await section.findByRole("alert")).toHaveTextContent("The file is not JSON.");
  expect(calls).toEqual([]);
});
