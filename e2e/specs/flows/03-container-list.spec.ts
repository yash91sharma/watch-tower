// Flow 3 (task 16.8): the container list. Only the E2E Compose group is checked: the host
// can run other containers.
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

useSession();

const E2E_CONTAINERS = [
  "wt_test_e2e_healthy",
  "wt_test_e2e_json",
  "wt_test_e2e_latest",
  "wt_test_e2e_old_a",
  "wt_test_e2e_old_b",
  "wt_test_e2e_restart",
  "wt_test_e2e_tty",
  "wt_test_e2e_unhealthy",
];

test("the E2E group shows its containers by name, not the excluded one", async ({ page }) => {
  await page.goto("/");

  const group = page.getByRole("region", { name: "wt_test_e2e" });
  // Only the name links: the latest version is a link too.
  await expect(group.locator(`a[href^="/containers/"]`)).toHaveText(E2E_CONTAINERS);
  // wt.enable=false: the excluded test container, WT and the support services.
  for (const name of ["wt_test_e2e_excluded", "wt_test_e2e_wt", "wt_test_e2e_traefik", "wt_test_e2e_github"]) {
    await expect(page.getByRole("link", { name, exact: true })).toHaveCount(0);
  }
});

test("a row shows the state, the health and the status", async ({ page }) => {
  await page.goto("/");
  const group = page.getByRole("region", { name: "wt_test_e2e" });

  const healthy = group.getByRole("row").filter({ has: page.getByRole("link", { name: "wt_test_e2e_healthy" }) });
  await expect(healthy.getByRole("cell")).toHaveText(["wt_test_e2e_healthy", "running", "healthy", "1.0.0", "-", "no source", ""]);

  // The tag "latest" is not a version: WT does no check.
  const latest = group.getByRole("row").filter({ has: page.getByRole("link", { name: "wt_test_e2e_latest" }) });
  await expect(latest.getByRole("cell").nth(5)).toHaveText("no check");
});

test("the latest version links to its GitHub release in a new tab", async ({ page }) => {
  await page.goto("/");
  const group = page.getByRole("region", { name: "wt_test_e2e" });

  const link = group.getByRole("link", { name: "1.0.0", exact: true }).first();
  await expect(link).toHaveAttribute("href", /^https:\/\/github\.com\/wt-e2e\/.+\/releases\/tag\/1\.0\.0$/);
  await expect(link).toHaveAttribute("target", "_blank");
});
