// Flow 5 (task 16.10): Check now with one new release on the fake GitHub. The UI shows the
// versions, the notes and the LLM summary. ntfy gets one message with the WT link. A
// second run sends nothing.
import { expect, type Page, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";
import { changeSettings } from "../../helpers/settings";
import { addRelease, LLM_URL, NTFY_URL, ntfyMessages } from "../../helpers/stack";

useSession();

const TOPIC = "wt-e2e-flow5";

async function checkNow(page: Page) {
  await page.goto("/");
  const button = page.getByRole("button", { name: "Check now", exact: true });
  await expect(button).toBeEnabled();
  await button.click();
  // The run ends when the button is on again (the stream refetches the status).
  await expect(button).toBeEnabled({ timeout: 60_000 });
  await expect(page.getByText(/^Last check: /)).toBeVisible();
}

test("Check now shows the update and sends one ntfy message", async ({ page }) => {
  await changeSettings(page.request, {
    ntfy_url: NTFY_URL,
    ntfy_topic: TOPIC,
    llm_url: LLM_URL,
    llm_model: "fake",
    public_url: "https://wt.test",
  });
  await addRelease("wt-e2e/old-a", "1.1.0", "## 1.1.0\n- New dark mode");

  await checkNow(page);

  await expect.poll(() => ntfyMessages(TOPIC), { timeout: 30_000 }).toHaveLength(1);
  const [message] = await ntfyMessages(TOPIC);
  expect(message?.click).toBe("https://wt.test/containers/wt_test_e2e_old_a");

  await page.goto("/containers/wt_test_e2e_old_a");
  const update = page.getByRole("region", { name: "Update" });
  await expect(update.getByText("1.0.0", { exact: true })).toBeVisible();
  await expect(update.getByText("1.1.0", { exact: true })).toBeVisible();
  await expect(update.getByText("normal", { exact: true })).toBeVisible();
  await expect(update.getByText("Fake LLM summary.")).toBeVisible();
  await expect(update.getByTestId("release-notes")).toContainText("- New dark mode");
});

test("a second run sends nothing", async ({ page }) => {
  await checkNow(page);

  // Give WT time to send a (wrong) second message.
  await page.waitForTimeout(3000);
  expect(await ntfyMessages(TOPIC)).toHaveLength(1);
});

test("the Check now button of one app runs a check", async ({ page }) => {
  await page.goto("/");
  const button = page.getByRole("button", { name: "Check now: wt_test_e2e", exact: true });
  await expect(button).toBeEnabled();
  const before = await page.getByText(/^Last check: /).textContent();

  await button.click();

  await expect(button).toBeEnabled({ timeout: 60_000 });
  // A check of one app keeps the time of the last full check.
  await expect(page.getByText(/^Last check: /)).toHaveText(before ?? "");
});
