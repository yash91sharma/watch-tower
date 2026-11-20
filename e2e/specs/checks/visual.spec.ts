// Visual (task 16.19): screenshots of the main pages in light and dark mode, at desktop and
// phone width (the iphone project; pixel has the same width class, so it skips them).
// The baselines come from the Playwright image: bash e2e/run.sh --update-snapshots
// The apps screenshot covers only the E2E group. Times are masked. The sidebar list is
// masked: it shows all containers on the host Docker, and they change from host to host.
// The footer (the version) is masked. The metric values and charts change at each poll, and
// the Overview counts and app list show all host containers: they are masked too.
import { fileURLToPath } from "node:url";

import { expect, type Page, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

const MODES = ["light", "dark"] as const;

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name.endsWith("-pixel"), "The iphone project covers the phone width");
});

// The sidebar list (desktop only: on a phone the sidebar is closed).
const sidebar = (page: Page) => page.getByRole("navigation", { name: "Container list" });
// The footer shows the app version: it changes at each version bump.
const footer = (page: Page) => page.getByRole("contentinfo");

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
    test(`overview, ${colorScheme}`, async ({ page }) => {
      await open(page, "/", "Overview", colorScheme);
      const mask = [
        page.getByRole("region", { name: "Docker VM" }),
        page.getByRole("region", { name: "Apps" }),
        page.getByRole("main").getByRole("link", { name: /app|containers/ }),
        sidebar(page),
        footer(page),
      ];

      // Only the screen, not the full page: the app list below shows all host containers,
      // so the page height changes from host to host (the list is masked, its height is not).
      await expect(page).toHaveScreenshot(`overview-${colorScheme}.png`, { mask });
    });

    test(`apps, ${colorScheme}`, async ({ page }) => {
      await open(page, "/apps", "Apps", colorScheme);
      const group = page.getByRole("region", { name: "wt_test_e2e" });
      // The CPU and Memory columns (4 and 5), and the box of the sums in the group header
      // (it has a fixed width; the texts in it do not).
      const sums = group.getByText(/^CPU /).locator("xpath=..");
      const mask = [group.locator("td:nth-child(4), td:nth-child(5)"), sums];

      const stylePath = fileURLToPath(new URL("visual-apps.css", import.meta.url));

      await expect(group).toHaveScreenshot(`apps-${colorScheme}.png`, { mask, stylePath });
    });

    test(`container page, ${colorScheme}`, async ({ page }) => {
      await open(page, "/containers/wt_test_e2e_healthy", "wt_test_e2e_healthy", colorScheme);
      const events = page.getByRole("region", { name: "Events (last 7 days)" });
      const resources = page.getByRole("region", { name: "Resources" });
      await expect(resources.getByRole("heading", { name: "CPU" })).toBeVisible();

      await expect(page).toHaveScreenshot(`container-${colorScheme}.png`, {
        fullPage: true,
        mask: [events, resources, sidebar(page), footer(page)],
      });
    });

    test(`settings, ${colorScheme}`, async ({ page }) => {
      await open(page, "/settings", "Settings", colorScheme);

      await expect(page).toHaveScreenshot(`settings-${colorScheme}.png`, { fullPage: true, mask: [sidebar(page), footer(page)] });
    });

    test(`logs page, ${colorScheme}`, async ({ page }) => {
      await open(page, "/containers/wt_test_e2e_json/logs", "Logs: wt_test_e2e_json", colorScheme);
      const log = page.getByRole("log");
      await expect(log.locator("[data-index]").first()).toBeVisible();

      // The lines change on each run: mask them.
      await expect(page).toHaveScreenshot(`logs-${colorScheme}.png`, { fullPage: true, mask: [log, sidebar(page), footer(page)] });
    });

    test(`not found page, ${colorScheme}`, async ({ page }) => {
      await open(page, "/no/such/page", "Page not found", colorScheme);

      await expect(page).toHaveScreenshot(`not-found-${colorScheme}.png`, { fullPage: true, mask: [sidebar(page), footer(page)] });
    });
  }
});
