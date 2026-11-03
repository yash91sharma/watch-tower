// Flow 10 (task 16.15): change settings, export, delete the DB, restart WT, set up again,
// import the file, export again: the same file.
import { readFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

import { setUp, useSession } from "../../helpers/admin";
import { deleteWtData } from "../../helpers/stack";

useSession();

async function exportFile(page: Page): Promise<{ name: string; text: string }> {
  await page.goto("/settings");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Export" }).click()]);
  return { name: download.suggestedFilename(), text: readFileSync(await download.path(), "utf8") };
}

test("export, a new install and an import give the same file", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("Check interval (hours)").fill("12");
  await page.getByLabel("ntfy topic").fill("wt-e2e-flow10");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  const first = await exportFile(page);
  expect(first.name).toMatch(/^wt-config-\d{4}-\d{2}-\d{2}\.json$/);
  expect(first.text).toContain('"check_interval_hours":12');
  expect(first.text).not.toMatch(/token|api_key|password/i);

  await deleteWtData();
  await page.goto("/");
  await expect(page).toHaveURL(/\/setup$/);
  await setUp(page);

  await page.goto("/settings");
  await page.getByLabel("Config file").setInputFiles({ name: "wt.json", mimeType: "application/json", buffer: Buffer.from(first.text) });
  await expect(page.getByText(/^\d+ settings, /)).toBeVisible();
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByText("Imported.")).toBeVisible();
  await expect(page.getByLabel("Check interval (hours)")).toHaveValue("12");

  const second = await exportFile(page);
  expect(second.text).toBe(first.text);
});
