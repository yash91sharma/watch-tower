// The admin of the E2E run. Flow 1 sets it up, the next flows log in with it. A state file
// keeps it (and the last used TOTP step), because a worker restarts after a failed test.
import { readFileSync, writeFileSync } from "node:fs";

import { expect, type Page } from "@playwright/test";

import { totp } from "./totp";

const STATE_FILE = "/tmp/wt-e2e-state.json";
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
