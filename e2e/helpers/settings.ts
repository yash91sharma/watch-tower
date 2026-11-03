// WT settings through the API, with the session of the page (logged in).
import type { APIRequestContext } from "@playwright/test";

/** Change some settings. The other settings keep their values. */
export async function changeSettings(request: APIRequestContext, values: Record<string, unknown>): Promise<void> {
  const current = (await (await request.get("/api/settings")).json()) as { values: Record<string, unknown> };
  const response = await request.put("/api/settings", { data: { ...current.values, ...values } });
  if (!response.ok()) throw new Error(`PUT /api/settings: ${String(response.status())} ${await response.text()}`);
}

/** Restart loop window M = `minutes`, so that a flow does not wait 10 minutes. */
export async function setRestartWindow(request: APIRequestContext, minutes: number): Promise<void> {
  await changeSettings(request, { restart_window_minutes: minutes });
}
