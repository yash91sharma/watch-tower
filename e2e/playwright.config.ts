// E2E tests against the stack of compose.test.yaml (run them with run.sh).
//  - flows: the flows (specs/flows) on Chromium at desktop size, one at a time, in order.
//    They change the WT state.
//  - <browser>-<size>: read-only checks (specs/checks: smoke, accessibility, visual) on
//    Chromium and WebKit at desktop, iPhone and Pixel sizes. They run after flows.
import { defineConfig, devices } from "@playwright/test";

const SIZES = {
  desktop: devices["Desktop Chrome"],
  iphone: devices["iPhone 15"],
  pixel: devices["Pixel 7"],
};
const BROWSERS = ["chromium", "webkit"] as const;

export default defineConfig({
  testDir: "specs",
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "https://wt.test",
    // Traefik in the stack has a self-signed certificate.
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "flows",
      testMatch: ["sample.spec.ts", "flows/**/*.spec.ts"],
      // A login can wait up to 30 s for a new TOTP step. WT restarts and checks take time too.
      timeout: 120_000,
      use: { ...devices["Desktop Chrome"] },
    },
    // Only with FOOTPRINT=1 run.sh: it needs the footprint containers. No flows first:
    // the 50 more containers would change the flow 3 list.
    ...(process.env.FOOTPRINT
      ? [
          {
            name: "footprint",
            testMatch: ["footprint/**/*.spec.ts"],
            timeout: 180_000,
            use: { ...devices["Desktop Chrome"] },
          },
        ]
      : []),
    ...BROWSERS.flatMap((browserName) =>
      Object.entries(SIZES).map(([size, device]) => ({
        name: `${browserName}-${size}`,
        testMatch: ["sample.spec.ts", "checks/**/*.spec.ts"],
        dependencies: ["flows"],
        use: { ...device, browserName },
      })),
    ),
  ],
});
