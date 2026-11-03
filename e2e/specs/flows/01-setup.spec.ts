// Flow 1 (task 16.6): first setup with the token from the WT log, a password and TOTP.
import { expect, test } from "@playwright/test";

import { setUp } from "../../helpers/admin";

test("setup with the token, a password and a TOTP code opens the app", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/setup$/);

  await setUp(page);

  await expect(page).toHaveURL(/\/$/);
});

test("the setup token does not work a second time", async ({ page }) => {
  await page.goto("/setup");

  // The admin exists: the auth guard opens the login page.
  await expect(page).toHaveURL(/\/login$/);
});
