// PWA (task 16.20): a valid manifest, the service worker registers, the app shell loads
// offline, and no /api answer is in a cache. Chromium desktop only (service worker support
// in Playwright).
import { expect, test } from "@playwright/test";

// Chromium does not register a service worker on a site with a certificate error, and
// ignoreHTTPSErrors does not change that. The stack has a self-signed certificate.
test.use({ launchOptions: { args: ["--ignore-certificate-errors"] } });

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "chromium-desktop", "Service worker tests run on Chromium desktop");
});

test("the manifest is valid and its icons exist", async ({ request }) => {
  const manifest = (await (await request.get("/manifest.webmanifest")).json()) as {
    name: string;
    display: string;
    start_url: string;
    icons: { src: string; purpose?: string }[];
  };

  expect(manifest).toMatchObject({ name: "WT", display: "standalone", start_url: "/" });
  expect(manifest.icons.some((icon) => icon.purpose === "maskable")).toBe(true);
  for (const icon of manifest.icons) {
    const response = await request.get(`/${icon.src}`);
    expect(response.headers()["content-type"]).toBe("image/png");
  }
});

test("the service worker registers, the shell loads offline, /api is not cached", async ({ page, context }) => {
  await page.goto("/login");
  await expect
    .poll(() => page.evaluate(async () => (await navigator.serviceWorker.ready).active?.state))
    .toBe("activated");
  // The service worker controls the page after a reload.
  await page.reload();
  await page.getByRole("heading", { level: 1, name: "Log in" }).waitFor();

  await context.setOffline(true);
  await page.reload();

  // The app shell (HTML and JS) comes from the cache, so React renders. The API does not:
  // TanStack Query waits for the network, so the auth guard shows its loading text.
  await expect(page).toHaveTitle("WT");
  await expect(page.getByText("Loading…")).toBeVisible();
  const api = await page.evaluate(() =>
    fetch("/api/health").then(
      (response) => response.status,
      () => "failed",
    ),
  );
  expect(api).toBe("failed");
  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      for (const request of await (await caches.open(name)).keys()) urls.push(new URL(request.url).pathname);
    }
    return urls;
  });
  expect(cached).toContain("/index.html");
  expect(cached.filter((path) => path.startsWith("/api/"))).toEqual([]);
  await context.setOffline(false);
});
