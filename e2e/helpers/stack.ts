// Helpers for the E2E stack (compose.test.yaml). The runner has the Docker CLI and the host
// Docker socket, and it is on the e2e network (it reaches github:8000, llm:8000, ntfy:80).
import { execFileSync } from "node:child_process";

export const WT = "wt_test_e2e_wt";
export const GITHUB_URL = "http://github:8000";
export const LLM_URL = "http://llm:8000";
export const NTFY_URL = "http://ntfy";

export function docker(...args: string[]): string {
  return execFileSync("docker", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** The newest setup token in the WT log. */
export function setupToken(): string {
  // WT logs to stdout.
  const tokens = [...docker("logs", WT).matchAll(/use this setup token: (\S+)/g)].map((match) => match[1]);
  const token = tokens.at(-1);
  if (!token) throw new Error("No setup token in the WT log");
  return token;
}

/** Restart WT and wait until it is healthy. */
export async function restartWt(): Promise<void> {
  docker("restart", WT);
  await waitHealthy();
}

async function waitHealthy(): Promise<void> {
  for (let tries = 0; tries < 60; tries++) {
    if (docker("inspect", "-f", "{{.State.Health.Status}}", WT).trim() === "healthy") return;
    await sleep(1000);
  }
  throw new Error("WT is not healthy after the restart");
}

/** Make all sessions old: last use `days` ago, and expired. */
export function ageSessions(days: number): void {
  const code = [
    "import datetime as d, sqlite3",
    `t = (d.datetime.now(d.UTC) - d.timedelta(days=${String(days)})).strftime('%Y-%m-%d %H:%M:%S.%f')`,
    "c = sqlite3.connect('/data/wt.db')",
    "c.execute('UPDATE session SET last_seen = ?, expires = ?', (t, t))",
    "c.commit()",
  ].join("; ");
  docker("exec", WT, "python", "-c", code);
}

/** Fake GitHub: add a release as the newest one. */
export async function addRelease(repo: string, tag: string, body = ""): Promise<void> {
  const response = await fetch(`${GITHUB_URL}/_control/repos/${repo}/releases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag_name: tag, body }),
  });
  if (!response.ok) throw new Error(`Fake GitHub: ${String(response.status)}`);
}

/** Fake LLM: set the mode (good, slow or error). */
export async function setLlmMode(mode: "good" | "slow" | "error"): Promise<void> {
  await fetch(`${LLM_URL}/_control/mode`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
}

export interface NtfyMessage {
  title?: string;
  message?: string;
  priority?: number;
  click?: string;
}

/** All messages of an ntfy topic (JSON poll API). */
export async function ntfyMessages(topic: string): Promise<NtfyMessage[]> {
  const response = await fetch(`${NTFY_URL}/${topic}/json?poll=1&since=all`);
  const text = await response.text();
  return text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as NtfyMessage & { event: string })
    .filter((item) => item.event === "message");
}

/** Stop WT, delete its DB (wt.db and the WAL files) and start WT again: a new install. */
export async function deleteWtData(): Promise<void> {
  const image = docker("inspect", "-f", "{{.Config.Image}}", WT).trim();
  docker("stop", WT);
  docker("run", "--rm", "--entrypoint", "sh", "--volumes-from", WT, image, "-c", "rm -f /data/wt.db /data/wt.db-wal /data/wt.db-shm");
  docker("start", WT);
  await waitHealthy();
}
