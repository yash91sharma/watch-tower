// Flow 14 (resource metrics, task 4.1): the Overview, the CPU and memory on App details,
// the Resources charts of a container and the shared chart range. Flow 10 set the poll
// interval to 5 s. A CPU % needs 2 polls.
import { expect, test } from "@playwright/test";

import { useSession } from "../../helpers/admin";

useSession();

const CPU_LABEL = /^\d+(\.\d)?% \(\d+\.\d{1,2} cores?\)$/;

test("the Overview shows the VM values and the counts", async ({ page }) => {
  await page.goto("/");
  const vm = page.getByRole("region", { name: "Docker VM" });

  await expect(vm.getByText(CPU_LABEL)).toBeVisible({ timeout: 30_000 });
  await expect(vm.getByRole("meter", { name: "Memory" })).toBeVisible();
  await expect(vm.getByRole("img", { name: "CPU chart" })).toBeVisible();
  const main = page.getByRole("main");
  await expect(main.getByRole("link", { name: /^\d+ apps?$/ })).toBeVisible();
  await expect(main.getByRole("link", { name: /^\d+ running of \d+ containers$/ })).toBeVisible();
  const apps = page.getByRole("region", { name: "Apps" });
  await expect(apps.getByRole("link", { name: "wt_test_e2e", exact: true })).toHaveAttribute("href", "/apps?group=wt_test_e2e");
});

test("App details shows the CPU and memory of a running container", async ({ page }) => {
  await page.goto("/apps");
  const group = page.getByRole("region", { name: "wt_test_e2e" });
  const row = group.getByRole("row").filter({ has: page.getByRole("link", { name: "wt_test_e2e_healthy" }) });

  await expect(row.getByRole("cell").nth(3)).toHaveText(CPU_LABEL, { timeout: 30_000 });
  await expect(row.getByRole("cell").nth(4)).toHaveText(/^[\d.]+ (B|KiB|MiB|GiB)$/);
  await expect(row.getByRole("link", { name: "Logs of wt_test_e2e_healthy" })).toHaveAttribute(
    "href",
    "/containers/wt_test_e2e_healthy/logs",
  );
});

test("the container page shows the Resources charts", async ({ page }) => {
  await page.goto("/containers/wt_test_e2e_healthy");
  const resources = page.getByRole("region", { name: "Resources" });

  for (const title of ["CPU", "Memory", "Network", "Disk I/O"]) {
    await expect(resources.getByRole("img", { name: `${title} chart` }).locator("canvas")).toBeVisible();
  }
});

test("a range change on one chart changes all charts, also on the container page", async ({ page }) => {
  await page.goto("/");
  const selects = page.getByRole("region", { name: "Docker VM" }).getByRole("combobox", { name: "Range" });
  await expect(selects).toHaveCount(5);

  await selects.first().selectOption("6h");

  for (const select of await selects.all()) await expect(select).toHaveValue("6h");
  await page.goto("/containers/wt_test_e2e_healthy");
  await expect(page.getByRole("combobox", { name: "Range" }).first()).toHaveValue("6h");
  // Back to the default for the checks after the flows.
  await page.getByRole("combobox", { name: "Range" }).first().selectOption("1h");
});
