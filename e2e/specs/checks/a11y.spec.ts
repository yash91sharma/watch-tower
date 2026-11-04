// Accessibility (task 16.18): axe on each page, in light and dark mode. No serious or
// critical issue. The setup page is not here: after the flows an admin exists, so the app
// opens the login page (the setup form uses the same components).
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

const MODES = ["light", "dark"] as const;

async function expectNoSeriousIssues(page: Page) {
  // No CSS transitions: axe must not measure a color in the middle of a change.
  await page.addStyleTag({ content: "*, *::before, *::after { transition: none !important; animation: none !important; }" });
  const results = await new AxeBuilder({ page }).analyze();
  const issues = results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => `${violation.id}: ${violation.help} (${violation.nodes.map((node) => node.target.join(" ")).join(", ")})`);
  expect(issues).toEqual([]);
}

for (const colorScheme of MODES) {
  test(`login page, ${colorScheme} mode`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto("/login");
    await expect(page.getByRole("heading", { level: 1, name: "Log in" })).toBeVisible();

    await expectNoSeriousIssues(page);
  });
}

test.describe("logged in", () => {
  useSession();

  const PAGES = [
    ["/", "Containers"],
    ["/containers/wt_test_e2e_old_a", "wt_test_e2e_old_a"],
    ["/containers/wt_test_e2e_json/logs", "Logs: wt_test_e2e_json"],
    ["/settings", "Settings"],
    ["/no/such/page", "Page not found"],
  ] as const;

  for (const colorScheme of MODES) {
    for (const [path, heading] of PAGES) {
      test(`${path}, ${colorScheme} mode`, async ({ page }) => {
        await page.emulateMedia({ colorScheme });
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        // Wait for the data (the page shows "Loading…" first).
        await expect(page.getByText("Loading", { exact: false })).toHaveCount(0);

        await expectNoSeriousIssues(page);
      });
    }
  }
});
