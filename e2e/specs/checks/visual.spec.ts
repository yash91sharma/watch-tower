// Visual (task 16.19): screenshots of the main pages in light and dark mode, at desktop and
// phone width (the iphone project; pixel has the same width class, so it skips them).
// The baselines come from the Playwright image: bash e2e/run.sh --update-snapshots
// The containers screenshot covers only the E2E group. Times are masked. The sidebar list is
// masked: it shows all containers on the host Docker, and they change from host to host.
import { expect, type Page, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

const MODES = ["light", "dark"] as const;

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name.endsWith("-pixel"), "The iphone project covers the phone width");
});

// The sidebar list (desktop only: on a phone the sidebar is closed).
const sidebar = (page: Page) => page.getByRole("navigation", { name: "Container list" });

async function open(page: Page, path: string, heading: string, colorScheme: (typeof MODES)[number]) {
  await page.emulateMedia({ colorScheme });
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await expect(page.getByText("Loading", { exact: false })).toHaveCount(0);
}

for (const colorScheme of MODES) {
  test(`login page, ${colorScheme}`, async ({ page }) => {
    await open(page, "/login", "Log in", colorScheme);

    await expect(page).toHaveScreenshot(`login-${colorScheme}.png`, { fullPage: true });
  });
}

test.describe("logged in", () => {
  useSession();

  for (const colorScheme of MODES) {
    test(`containers, ${colorScheme}`, async ({ page }) => {
      await open(page, "/", "Containers", colorScheme);

      await expect(page.getByRole("region", { name: "wt_test_e2e" })).toHaveScreenshot(`containers-${colorScheme}.png`);
    });

    test(`container page, ${colorScheme}`, async ({ page }) => {
      await open(page, "/containers/wt_test_e2e_healthy", "wt_test_e2e_healthy", colorScheme);
      const events = page.getByRole("region", { name: "Events (last 7 days)" });

      await expect(page).toHaveScreenshot(`container-${colorScheme}.png`, { fullPage: true, mask: [events, sidebar(page)] });
    });

    test(`settings, ${colorScheme}`, async ({ page }) => {
      await open(page, "/settings", "Settings", colorScheme);

      await expect(page).toHaveScreenshot(`settings-${colorScheme}.png`, { fullPage: true, mask: [sidebar(page)] });
    });

    test(`logs page, ${colorScheme}`, async ({ page }) => {
      await open(page, "/containers/wt_test_e2e_json/logs", "Logs: wt_test_e2e_json", colorScheme);
      const log = page.getByRole("log");
      await expect(log.locator("[data-index]").first()).toBeVisible();

      // The lines change on each run: mask them.
      await expect(page).toHaveScreenshot(`logs-${colorScheme}.png`, { fullPage: true, mask: [log, sidebar(page)] });
    });

    test(`not found page, ${colorScheme}`, async ({ page }) => {
      await open(page, "/no/such/page", "Page not found", colorScheme);

      await expect(page).toHaveScreenshot(`not-found-${colorScheme}.png`, { fullPage: true, mask: [sidebar(page)] });
    });
  }
});
