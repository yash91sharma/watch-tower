// Flow 1 (task 16.6): first setup with the token from the WT log, a password and TOTP.
import { expect, test } from "@playwright/test";

import { freshTotp, PASSWORD, saveSecret } from "../../helpers/admin";
import { setupToken } from "../../helpers/stack";

test("setup with the token, a password and a TOTP code opens the app", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/setup$/);

  await page.getByLabel("Setup token").fill(setupToken());
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByRole("img", { name: "QR code for the authenticator app" })).toBeVisible();
  const secret = (await page.getByText(/^Secret:/).locator("code").textContent()) ?? "";
  expect(secret).toMatch(/^[A-Z2-7]+$/);
  saveSecret(secret);

  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Password again").fill(PASSWORD);
  await page.getByLabel("TOTP code").fill(await freshTotp(secret));
  await page.getByRole("button", { name: "Set up" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Containers" })).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
});

test("the setup token does not work a second time", async ({ page }) => {
  await page.goto("/setup");

  // The admin exists: the auth guard opens the login page.
  await expect(page).toHaveURL(/\/login$/);
});
