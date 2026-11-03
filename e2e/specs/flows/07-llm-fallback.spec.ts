// Flow 7 (task 16.12): with the LLM off, and with an LLM that times out, the update shows
// the notes only (no summary) and the keyword severity ("security" gives critical).
import { expect, type Page, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";
import { changeSettings } from "../../helpers/settings";
import { addRelease, LLM_URL, setLlmMode } from "../../helpers/stack";

useSession();

async function llmRequests(): Promise<number> {
  const response = await fetch(`${LLM_URL}/_control/requests`);
  return ((await response.json()) as { count: number }).count;
}

/** Click Check now and wait until the run ends (a new last run time, not running). */
async function checkNowAndWait(page: Page, timeout: number) {
  const status = async () =>
    (await (await page.request.get("/api/checks/status")).json()) as { running: boolean; last_run: string | null };
  const before = (await status()).last_run;
  await page.goto("/");
  await page.getByRole("button", { name: "Check now" }).click();
  await expect
    .poll(
      async () => {
        const now = await status();
        return !now.running && now.last_run !== before;
      },
      { timeout },
    )
    .toBe(true);
}

async function expectNotesOnly(page: Page, name: string, tag: string) {
  await page.goto(`/containers/${name}`);
  const update = page.getByRole("region", { name: "Update" });
  await expect(update.getByText(tag, { exact: true })).toBeVisible();
  await expect(update.getByText("critical", { exact: true })).toBeVisible();
  await expect(update.getByTestId("release-notes")).toContainText("security fix");
  await expect(update.getByText("Fake LLM summary.")).toHaveCount(0);
}

test("with the LLM off, WT shows the notes and the keyword severity", async ({ page }) => {
  await changeSettings(page.request, { llm_url: null, llm_model: null });
  const before = await llmRequests();
  await addRelease("wt-e2e/old-b", "2.2.0", "## 2.2.0\n- A security fix");

  await checkNowAndWait(page, 60_000);

  await expectNotesOnly(page, "wt_test_e2e_old_b", "2.2.0");
  expect(await llmRequests()).toBe(before);
});

test("with an LLM that times out, WT shows the notes and the keyword severity", async ({ page }) => {
  // WT waits 60 s for the LLM.
  test.setTimeout(240_000);
  await changeSettings(page.request, { llm_url: LLM_URL, llm_model: "fake" });
  await setLlmMode("slow");
  try {
    await addRelease("wt-e2e/old-a", "1.3.0", "## 1.3.0\n- Another security fix");

    await checkNowAndWait(page, 180_000);

    await expectNotesOnly(page, "wt_test_e2e_old_a", "1.3.0");
  } finally {
    await setLlmMode("good");
  }
});
