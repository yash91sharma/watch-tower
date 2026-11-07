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

test("with no session, the app opens the login page", async ({ page }) => {
  await page.goto("/settings");

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { level: 1, name: "Log in" })).toBeVisible();
});

test("with no session, the data routes give 401 and health gives 200", async ({ request }) => {
  expect((await request.get("/api/health")).status()).toBe(200);
  for (const path of ["/api/containers", "/api/settings", "/api/config/export"]) {
    expect((await request.get(path)).status(), path).toBe(401);
  }
});

test("the app sends the security headers", async ({ request }) => {
  const headers = (await request.get("/login")).headers();

  expect(headers["content-security-policy"]).toBeTruthy();
  expect(headers["x-content-type-options"]).toBe("nosniff");
});

test.describe("logged in", () => {
  useSession();

  test("the list shows the E2E group", async ({ page }) => {
    await page.goto("/");

    const group = page.getByRole("region", { name: "wt_test_e2e" });
    await expect(group.getByRole("link", { name: "wt_test_e2e_healthy" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Check now", exact: true })).toBeVisible();
  });

  test("a container page shows its parts", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("main").getByRole("link", { name: "wt_test_e2e_old_a" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "wt_test_e2e_old_a" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Release source" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Update" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Events (last 7 days)" })).toBeVisible();
  });

  test("the logs page shows live lines", async ({ page }) => {
    await page.goto("/containers/wt_test_e2e_json");
    await page.getByRole("main").getByRole("link", { name: "Logs" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "Logs: wt_test_e2e_json" })).toBeVisible();
    await expect(page.getByRole("log").locator("[data-index]").first()).toBeVisible();
  });

  test("the sidebar marks the open page and opens another container", async ({ page }) => {
    await page.goto("/containers/wt_test_e2e_json/logs");
    // On a small screen the sidebar is closed until the admin opens it.
    if ((page.viewportSize()?.width ?? 0) < 768) await page.getByRole("button", { name: "Sidebar" }).click();
    const sidebar = page.getByRole("navigation", { name: "Container list" });

    await expect(sidebar.getByRole("link", { name: "Logs" })).toHaveAttribute("aria-current", "page");
    await sidebar.getByRole("link", { name: "wt_test_e2e_healthy" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "wt_test_e2e_healthy" })).toBeVisible();
  });

  test("the latest tag shows 'no check'", async ({ page }) => {
    await page.goto("/");

    const row = page.getByRole("row").filter({ has: page.getByRole("link", { name: "wt_test_e2e_latest" }) });
    await expect(row.getByText("no check")).toBeVisible();
  });

  test("the excluded container is not in the list", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("main").getByRole("link", { name: "wt_test_e2e_healthy" })).toBeVisible();
    await expect(page.getByRole("link", { name: "wt_test_e2e_excluded" })).toHaveCount(0);
  });

  test("the settings page shows its form and export", async ({ page }) => {
    await page.goto("/settings");

    await expect(page.getByLabel("Check interval (hours)")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" }).first()).toBeVisible();
    await expect(page.getByRole("region", { name: "Export and import" })).toBeVisible();
  });

  test("the log search finds a line", async ({ page }) => {
    await page.goto("/containers/wt_test_e2e_json/logs");
    await expect(page.getByRole("log").locator("[data-index]").first()).toBeVisible();

    await page.getByLabel("Search").fill("zz-no-such-text-zz");

    await expect(page.getByText("No match")).toBeVisible();
  });

  test("an unknown path shows the not found page", async ({ page }) => {
    await page.goto("/no/such/page");

    await expect(page.getByRole("heading", { level: 1, name: "Page not found" })).toBeVisible();
    await page.getByRole("link", { name: "Open the container list" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Containers" })).toBeVisible();
  });
});
