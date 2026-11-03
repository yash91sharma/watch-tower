// The admin of the E2E run. Flow 1 sets it up, the next flows log in with it. A state file
// keeps it (and the last used TOTP step), because a worker restarts after a failed test.
import { existsSync, readFileSync, writeFileSync } from "node:fs";

import { type Browser, type BrowserContext, expect, type Page, test } from "@playwright/test";

import { setupToken } from "./stack";
import { totp } from "./totp";

const STATE_FILE = "/tmp/wt-e2e-state.json";
// Same as baseURL in playwright.config.ts (a new browser context does not get it).
const BASE_URL = "https://wt.test";
export const PASSWORD = "e2e-password-1234";

interface State {
  secret?: string;
  lastStep?: number;
}

function readState(): State {
  try {
    return JSON.parse(readFileSync(STATE_FILE, "utf8")) as State;
  } catch {
    return {};
  }
}

function writeState(changes: State): void {
  writeFileSync(STATE_FILE, JSON.stringify({ ...readState(), ...changes }));
}

export function saveSecret(secret: string): void {
  writeState({ secret });
}

export function savedSecret(): string {
  const { secret } = readState();
  if (!secret) throw new Error("No admin: run flow 1 (setup) first");
  return secret;
}

const currentStep = () => Math.floor(Date.now() / 30_000);

/**
 * A TOTP code that WT did not see yet. WT rejects a step that it already used (replay),
 * so this waits for the next step when needed (up to 30 s).
 */
export async function freshTotp(secret = savedSecret()): Promise<string> {
  const last = readState().lastStep ?? 0;
  while (currentStep() <= last) await new Promise((resolve) => setTimeout(resolve, 500));
  const step = currentStep();
  writeState({ lastStep: step });
  return totp(secret, step);
}

/** The first setup on the setup page: token from the WT log, password, TOTP. Saves the secret. */
export async function setUp(page: Page): Promise<void> {
  await page.goto("/setup");
  await page.getByLabel("Setup token").fill(setupToken());
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByRole("img", { name: "QR code for the authenticator app" })).toBeVisible();
  const secret = (await page.getByText(/^Secret:/).locator("code").textContent()) ?? "";
  expect(secret).toMatch(/^[A-Z2-7]+$/);
  saveSecret(secret);

  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Password again").fill(PASSWORD);
  await page.getByLabel("TOTP code").fill(await freshTotp(secret));
  await page.getByRole("button", { name: "Set up" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Containers" })).toBeVisible();
}

/** Log in on the login page with the admin password and a fresh TOTP code. */
export async function logIn(page: Page, password = PASSWORD): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("TOTP code").fill(await freshTotp());
  await page.getByRole("button", { name: "Log in" }).click();
}

/** Log in and wait for the container list. */
export async function logInOk(page: Page): Promise<void> {
  await logIn(page);
  await expect(page.getByRole("heading", { level: 1, name: "Containers" })).toBeVisible();
}

/** A saved login (cookies). useSession() puts it in each test. */
const SESSION_FILE = "/tmp/wt-e2e-session.json";

type Cookies = Parameters<BrowserContext["addCookies"]>[0];

/** Call it in a spec file: each test of the file starts logged in. */
export function useSession(): void {
  test.beforeEach(async ({ browser, context }) => {
    await saveSession(browser);
    const { cookies } = JSON.parse(readFileSync(SESSION_FILE, "utf8")) as { cookies: Cookies };
    await context.addCookies(cookies);
  });
}

/**
 * Make SESSION_FILE hold a valid session. It logs in only if the saved session does not
 * work any more, so that the flows do not wait for a new TOTP step each time.
 */
async function saveSession(browser: Browser): Promise<void> {
  const options = { baseURL: BASE_URL, ignoreHTTPSErrors: true };
  if (existsSync(SESSION_FILE)) {
    const saved = await browser.newContext({ ...options, storageState: SESSION_FILE });
    const state = (await (await saved.request.get("/api/auth/state")).json()) as { logged_in: boolean };
    await saved.close();
    if (state.logged_in) return;
  }
  const context = await browser.newContext(options);
  await logInOk(await context.newPage());
  await context.storageState({ path: SESSION_FILE });
  await context.close();
}
