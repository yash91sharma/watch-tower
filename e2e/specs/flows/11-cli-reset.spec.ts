// Flow 11 (task 16.16): `wt reset-admin` in the WT container, then a WT restart: the app
// opens the setup page. The flow then sets up the admin again for the next flows.
import { expect, test } from "@playwright/test";

import { setUp, useSession } from "../../helpers/admin";
import { docker, restartWt, WT } from "../../helpers/stack";

useSession();

test("reset-admin and a restart open the setup page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Containers" })).toBeVisible();

  const output = docker("exec", WT, "wt", "reset-admin");
  expect(output).toContain("Restart WT (docker restart wt)");
  await restartWt();

  // The old session does not work any more, and there is no admin.
  await page.goto("/");
  await expect(page).toHaveURL(/\/setup$/);
  await setUp(page);
  await expect(page).toHaveURL(/\/$/);
});
