// Smoke (tasks 16.5 and 18.1): the main pages work on each browser and size. Read-only:
// it runs after the flows, with their admin.
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

test("the login page shows its form", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await expect(page.getByLabel("TOTP code")).toBeVisible();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
});

test.describe("logged in", () => {
  useSession();

  test("the list shows the E2E group", async ({ page }) => {
    await page.goto("/");

    const group = page.getByRole("region", { name: "wt_test_e2e" });
    await expect(group.getByRole("link", { name: "wt_test_e2e_healthy" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Check now" })).toBeVisible();
  });

  test("a container page shows its parts", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "wt_test_e2e_old_a" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "wt_test_e2e_old_a" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Release source" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Update" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Events (last 7 days)" })).toBeVisible();
  });

  test("the logs page shows live lines", async ({ page }) => {
    await page.goto("/containers/wt_test_e2e_json");
    await page.getByRole("link", { name: "Logs" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "Logs: wt_test_e2e_json" })).toBeVisible();
    await expect(page.getByRole("log").locator("[data-index]").first()).toBeVisible();
  });
});
