// Flow 9 (task 16.14): the logs of wt_test_e2e_json (a JSON line on stdout and an "error
// line" on stderr each second): live tail, search, JSON pretty-print, download and the way back.
import { readFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

useSession();

const rows = (page: Page) => page.getByRole("log").locator("[data-index]");

test.beforeEach(async ({ page }) => {
  await page.goto("/containers/wt_test_e2e_json/logs");
  await expect(page.getByRole("heading", { level: 1, name: "Logs: wt_test_e2e_json" })).toBeVisible();
  await expect(rows(page).first()).toBeVisible();
});

test("the live tail adds new lines, stderr in another color", async ({ page }) => {
  const last = await rows(page).last().textContent();

  await expect(rows(page).last()).not.toHaveText(last ?? "", { timeout: 10_000 });

  await expect(rows(page).filter({ hasText: /^error line \d+$/ }).last()).toHaveClass(/text-destructive/);
  await expect(rows(page).filter({ hasText: /"msg":"tick"/ }).last()).not.toHaveClass(/text-destructive/);
});

test("search marks the matches, counts them and can show only them", async ({ page }) => {
  await page.getByLabel("Search").fill("ERROR LINE");

  await expect(page.getByText(/^\d+ of \d+$/)).toBeVisible();
  await expect(page.getByRole("log").locator("mark").first()).toHaveText("error line");

  await page.getByLabel("Only matches").check();
  for (const text of await rows(page).allTextContents()) expect(text).toMatch(/^error line \d+$/);
});

test("the JSON toggle formats the JSON lines only", async ({ page }) => {
  await page.getByLabel("Format JSON").check();

  await expect(rows(page).filter({ hasText: '"level": "info"' }).first()).toBeVisible();
  const json = (await rows(page).filter({ hasText: '"level": "info"' }).first().textContent()) ?? "";
  expect(json).toContain('{\n  "level": "info",\n');
  await expect(rows(page).filter({ hasText: /^error line \d+$/ }).first()).toBeVisible();
});

test("download gives the full log as a text file", async ({ page }) => {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download" }).click(),
  ]);

  expect(download.suggestedFilename()).toMatch(/^wt_test_e2e_json-\d{4}-\d{2}-\d{2}\.log$/);
  const text = readFileSync(await download.path(), "utf8");
  expect(text).toMatch(/^\S+ stdout \{"level":"info","n":1,"msg":"tick"\}$/m);
  expect(text).toMatch(/^\S+ stderr error line 1$/m);
});

test("the breadcrumb goes back to the container page", async ({ page }) => {
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "wt_test_e2e_json" }).click();

  await expect(page).toHaveURL(/\/containers\/wt_test_e2e_json$/);
  await expect(page.getByRole("heading", { level: 1, name: "wt_test_e2e_json" })).toBeVisible();
});
