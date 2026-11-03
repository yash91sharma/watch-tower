// Flow 8 (task 16.13): docker exec makes the test containers fail (see
// fakes/containers/README.md). Unhealthy, restart loop and each recovery send one ntfy
// message. The restart window M is 1 minute, so the loop recovery comes fast.
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";
import { changeSettings } from "../../helpers/settings";
import { docker, NTFY_URL, ntfyMessages } from "../../helpers/stack";

useSession();

const TOPIC = "wt-e2e-flow8";

async function titles(): Promise<string[]> {
  return (await ntfyMessages(TOPIC)).map((message) => message.title ?? "");
}

test.beforeAll(() => {
  // Start healthy, also after a failed run.
  docker("exec", "wt_test_e2e_unhealthy", "touch", "/tmp/ok");
  docker("exec", "wt_test_e2e_restart", "rm", "-f", "/tmp/crash");
});

test("unhealthy and the recovery send one message each", async ({ page }) => {
  await changeSettings(page.request, {
    ntfy_url: NTFY_URL,
    ntfy_topic: TOPIC,
    public_url: "https://wt.test",
    restart_window_minutes: 1,
  });

  docker("exec", "wt_test_e2e_unhealthy", "rm", "/tmp/ok");
  await expect.poll(titles, { timeout: 30_000 }).toContain("wt_test_e2e_unhealthy is unhealthy");
  await page.goto("/containers/wt_test_e2e_unhealthy");
  await expect(page.getByText("unhealthy", { exact: true })).toBeVisible();

  docker("exec", "wt_test_e2e_unhealthy", "touch", "/tmp/ok");
  await expect.poll(titles, { timeout: 30_000 }).toContain("wt_test_e2e_unhealthy is healthy again");

  expect(await titles()).toEqual(["wt_test_e2e_unhealthy is unhealthy", "wt_test_e2e_unhealthy is healthy again"]);
  await page.reload();
  const events = page.getByRole("region", { name: "Events (last 7 days)" });
  await expect(events.getByRole("listitem")).toHaveText([/Healthy again$/, /Unhealthy$/]);
});

test("a restart loop and its end send one message each", async () => {
  test.setTimeout(240_000);
  const before = (await titles()).length;

  // The app exits now and on the next 2 starts (restart: on-failure).
  docker("exec", "wt_test_e2e_restart", "sh", "-c", "echo 3 > /tmp/crash");
  await expect.poll(titles, { timeout: 60_000 }).toContain("wt_test_e2e_restart restarts in a loop");
  // No restart in M = 1 minute: the loop ends.
  await expect.poll(titles, { timeout: 150_000, intervals: [5000] }).toContain("wt_test_e2e_restart does not restart now");

  expect((await titles()).slice(before)).toEqual([
    "wt_test_e2e_restart restarts in a loop",
    "wt_test_e2e_restart does not restart now",
  ]);
});
