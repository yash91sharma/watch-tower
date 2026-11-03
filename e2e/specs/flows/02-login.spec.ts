// Flow 2 (task 16.7): login, logout, wrong password, wrong TOTP code, login limit (then a
// WT restart clears it), session expiry.
import { expect, type Page, test } from "@playwright/test";

import { logInOk, PASSWORD } from "../../helpers/admin";
import { ageSessions, restartWt } from "../../helpers/stack";

const FAILED = "The password or the TOTP code is not correct";

async function failedLogIn(page: Page, password: string, code: string) {
  await page.goto("/login");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("TOTP code").fill(code);
  await page.getByRole("button", { name: "Log in" }).click();
}

test("login opens the app, logout opens the login page", async ({ page }) => {
  await logInOk(page);

  await page.getByRole("button", { name: "Log out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});

test("a wrong password shows the error", async ({ page }) => {
  await failedLogIn(page, "not-the-password", "000000");

  await expect(page.getByRole("alert")).toHaveText(FAILED);
});

test("a wrong TOTP code shows the same error", async ({ page }) => {
  await failedLogIn(page, PASSWORD, "000000");

  await expect(page.getByRole("alert")).toHaveText(FAILED);
});

test("the login limit blocks with the wait time, and a WT restart clears it", async ({ page }) => {
  // 5 failures block. The tests above made 2.
  for (let attempt = 0; attempt < 6; attempt++) {
    await failedLogIn(page, "not-the-password", "000000");
    await expect(page.getByRole("alert")).toBeVisible();
    if ((await page.getByRole("alert").textContent())?.includes("Too many")) break;
  }
  await expect(page.getByRole("alert")).toHaveText(/Too many failed attempts\. Try again in 1[45] minutes\./);

  // WT keeps the count in memory.
  await restartWt();
  await logInOk(page);
});

test("an old session is not valid: the app opens the login page", async ({ page }) => {
  await logInOk(page);

  ageSessions(31);
  await page.reload();

  await expect(page).toHaveURL(/\/login$/);
});
