// Sample spec (task 16.5): it runs on all projects. WT answers through Traefik over HTTPS.
import { expect, test } from "@playwright/test";

test("the app loads over HTTPS", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle("Watch Tower");
  expect((await page.request.get("/api/health")).ok()).toBe(true);
});
