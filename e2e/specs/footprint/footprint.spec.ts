// Footprint (task 16.22, nightly): run with FOOTPRINT=1 bash e2e/run.sh --project footprint
// The stack then has 50 more test containers and wt_test_e2e_fast (1,000 log lines/s).
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";
import { docker, WT } from "../../helpers/stack";

useSession();

const MAX_RAM_MIB = 200;
const MAX_PAUSE_MS = 200;

/** The RAM of a container from docker stats, in MiB (for example "85.3MiB / 256MiB"). */
function ramMib(container: string): number {
  const used = docker("stats", "--no-stream", "--format", "{{.MemUsage}}", container).split("/")[0]?.trim() ?? "";
  const match = /^([\d.]+)(KiB|MiB|GiB)$/.exec(used);
  if (!match) throw new Error(`Cannot read the RAM: ${used}`);
  const factor = { KiB: 1 / 1024, MiB: 1, GiB: 1024 }[match[2] as "KiB" | "MiB" | "GiB"];
  return Number(match[1]) * factor;
}

test("with 50 more containers, WT uses less than 200 MB RAM when idle", async ({ page }) => {
  await page.goto("/");
  const group = page.getByRole("region", { name: "wt_test_e2e" });
  await expect(group.getByRole("link", { name: /^wt_test_e2e-filler-\d+$/ })).toHaveCount(50);
  // No open stream: WT is idle. Give it time to finish its start work.
  await page.close();
  await new Promise((resolve) => setTimeout(resolve, 30_000));

  const ram = ramMib(WT);

  console.log(`WT idle RAM: ${ram.toFixed(1)} MiB`);
  expect(ram).toBeLessThan(MAX_RAM_MIB);
});

test("after 5 s of 1,000 log lines/s, Pause updates the UI in less than 200 ms", async ({ page }) => {
  await page.goto("/containers/wt_test_e2e_fast/logs");
  await expect(page.getByRole("log").locator("[data-index]").first()).toBeVisible();
  await page.waitForTimeout(5000);

  // Time from the click to the next frame after the button changed (in the browser).
  const ms = await page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        const button = (name: string) => Array.from(document.querySelectorAll("button")).find((item) => item.textContent === name);
        const start = performance.now();
        const observer = new MutationObserver(() => {
          if (!button("Follow")) return;
          observer.disconnect();
          requestAnimationFrame(() => {
            resolve(performance.now() - start);
          });
        });
        observer.observe(document.body, { subtree: true, childList: true, characterData: true });
        button("Pause")?.click();
      }),
  );

  console.log(`Pause to UI update: ${ms.toFixed(0)} ms`);
  expect(ms).toBeLessThan(MAX_PAUSE_MS);
});
