// Flow 6 (task 16.11): new releases for two containers in one run, one with "CVE-" in the
// notes. ntfy gets one digest with high priority.
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";
import { changeSettings } from "../../helpers/settings";
import { addRelease, LLM_URL, NTFY_URL, ntfyMessages } from "../../helpers/stack";

useSession();

const TOPIC = "wt-e2e-flow6";
// ntfy JSON priority: 4 is "high".
const HIGH = 4;

test("two updates give one digest with high priority", async ({ page }) => {
  await changeSettings(page.request, {
    ntfy_url: NTFY_URL,
    ntfy_topic: TOPIC,
    llm_url: LLM_URL,
    llm_model: "fake",
    public_url: "https://wt.test",
  });
  await addRelease("wt-e2e/old-a", "1.2.0", "## 1.2.0\n- Fix CVE-2026-1234");
  await addRelease("wt-e2e/old-b", "2.1.0", "## 2.1.0\n- New API");

  await page.goto("/");
  await page.getByRole("button", { name: "Check now" }).click();

  await expect.poll(() => ntfyMessages(TOPIC), { timeout: 60_000 }).toHaveLength(1);
  const [digest] = await ntfyMessages(TOPIC);
  expect(digest?.title).toBe("2 updates");
  expect(digest?.priority).toBe(HIGH);
  expect(digest?.click).toBe("https://wt.test/");

  // The list shows both updates, the CVE one as critical.
  await page.reload();
  const group = page.getByRole("region", { name: "wt_test_e2e" });
  const row = (name: string) => group.getByRole("row").filter({ has: page.getByRole("link", { name }) });
  await expect(row("wt_test_e2e_old_a").getByRole("cell")).toHaveText([
    "wt_test_e2e_old_a",
    "running",
    "healthy",
    "1.0.0",
    "1.2.0",
    "update",
    "critical",
  ]);
  await expect(row("wt_test_e2e_old_b").getByRole("cell").nth(6)).toHaveText("normal");
});
