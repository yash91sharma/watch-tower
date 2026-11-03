// Flow 4 (task 16.9): the release source comes from the image label. The admin confirms it
// or edits it. The value stays after a reload.
import { expect, type Page, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

useSession();

const source = (page: Page) => page.getByRole("region", { name: "Release source" });

test("the label value shows as not confirmed until the admin confirms it", async ({ page }) => {
  await page.goto("/containers/wt_test_e2e_old_a");
  await expect(source(page).getByText("wt-e2e/old-a")).toBeVisible();
  await expect(source(page).getByText("not confirmed")).toBeVisible();

  await source(page).getByRole("button", { name: "Confirm" }).click();

  await expect(source(page).getByText("not confirmed")).toHaveCount(0);
  await page.reload();
  await expect(source(page).getByText("wt-e2e/old-a")).toBeVisible();
  await expect(source(page).getByText("not confirmed")).toHaveCount(0);
});

test("the admin edits the source with a GitHub URL", async ({ page }) => {
  await page.goto("/containers/wt_test_e2e_old_b");
  await source(page).getByRole("button", { name: "Edit" }).click();
  const input = source(page).getByLabel("GitHub URL or owner/repo");
  await expect(input).toHaveValue("wt-e2e/old-b");

  await input.fill("https://github.com/wt-e2e/old-b.git");
  await source(page).getByRole("button", { name: "Save" }).click();

  await expect(source(page).getByText("wt-e2e/old-b")).toBeVisible();
  await expect(source(page).getByText("not confirmed")).toHaveCount(0);
  await page.reload();
  await expect(source(page).getByText("wt-e2e/old-b")).toBeVisible();
});

test("a bad value shows the field error and changes nothing", async ({ page }) => {
  await page.goto("/containers/wt_test_e2e_healthy");
  await expect(source(page).getByText("No release source")).toBeVisible();
  await source(page).getByRole("button", { name: "Edit" }).click();

  await source(page).getByLabel("GitHub URL or owner/repo").fill("not a repo");
  await source(page).getByRole("button", { name: "Save" }).click();

  await expect(source(page).getByRole("alert")).toContainText("source: Give a GitHub URL or owner/repo");
  await page.reload();
  await expect(source(page).getByText("No release source")).toBeVisible();
});
