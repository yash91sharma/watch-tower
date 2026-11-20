// Shared MSW handlers: default API answers for all tests.
// A test changes an answer for itself with server.use(...).
import { http, HttpResponse, type HttpHandler } from "msw";

import type { History } from "@/api/types";

import { containerDetail, history, overview, settingsOut, sparklines } from "@/test/fixtures";

export const handlers: HttpHandler[] = [
  // The admin is logged in, so the auth guard opens the app.
  http.get("*/api/auth/state", () => HttpResponse.json({ setup_required: false, logged_in: true })),
  http.get("*/api/containers", () => HttpResponse.json([])),
  http.get("*/api/containers/:name", ({ params }) => HttpResponse.json(containerDetail({ name: String(params.name) }))),
  http.get("*/api/settings", () => HttpResponse.json(settingsOut())),
  http.get("*/api/metrics/overview", () => HttpResponse.json(overview())),
  http.get("*/api/metrics/sparklines", () => HttpResponse.json(sparklines())),
  http.get("*/api/metrics/vm/history", ({ request }) =>
    HttpResponse.json(history({ range: new URL(request.url).searchParams.get("range") as History["range"] })),
  ),
  http.get("*/api/metrics/containers/:name/history", ({ request }) =>
    HttpResponse.json(history({ range: new URL(request.url).searchParams.get("range") as History["range"] })),
  ),
  http.get("*/api/checks/status", () => HttpResponse.json({ running: false, last_run: null, counts: {} })),
];
