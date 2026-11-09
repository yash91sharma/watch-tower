// Flow 13: type the ntfy settings, do not save, send a test notification. ntfy gets it.
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";
import { NTFY_URL, ntfyMessages } from "../../helpers/stack";

useSession();

const TOPIC = "wt-e2e-flow13";

test("send test notification uses the form values and ntfy gets the message", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("ntfy URL").fill(NTFY_URL);
  await page.getByLabel("ntfy topic").fill(TOPIC);
  await page.getByRole("button", { name: "Send test notification" }).click();

  await expect(page.getByText("Sent. Look for it in ntfy.")).toBeVisible();
  expect((await ntfyMessages(TOPIC)).map((message) => message.title)).toEqual(["WT test notification"]);
});

test("send test notification shows the error when ntfy does not answer", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("ntfy URL").fill("http://127.0.0.1:9");
  await page.getByLabel("ntfy topic").fill(TOPIC);
  await page.getByRole("button", { name: "Send test notification" }).click();

  await expect(page.getByRole("alert")).toHaveText(/ntfy did not accept the message/);
});
