// Flow 12 (task 16.17): the socket proxy stops, so the Docker stream of WT stops. The banner
// shows, then the UI recovers when the proxy is back. WT sends no (false) ntfy message.
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";
import { changeSettings } from "../../helpers/settings";
import { docker, NTFY_URL, ntfyMessages } from "../../helpers/stack";

useSession();

const TOPIC = "wt-e2e-flow12";
const PROXY = "wt_test_e2e_socket_proxy";
const BANNER = "Docker is not connected. The data can be old.";

test.afterAll(() => {
  docker("start", PROXY);
});

test("the banner shows while Docker is not connected, then the UI recovers", async ({ page }) => {
  await changeSettings(page.request, { ntfy_url: NTFY_URL, ntfy_topic: TOPIC, public_url: "https://wt.test" });
  await page.goto("/");
  const group = page.getByRole("region", { name: "wt_test_e2e" });
  await expect(group.getByRole("link", { name: "wt_test_e2e_healthy" })).toBeVisible();

  docker("stop", PROXY);
  await expect(page.getByRole("status")).toHaveText(BANNER, { timeout: 30_000 });

  docker("start", PROXY);
  await expect(page.getByRole("status")).toHaveCount(0, { timeout: 60_000 });
  await expect(group.getByRole("link", { name: "wt_test_e2e_healthy" })).toBeVisible();

  // Give WT time to send a (false) message after the new container list.
  await page.waitForTimeout(5000);
  expect(await ntfyMessages(TOPIC)).toEqual([]);
});
