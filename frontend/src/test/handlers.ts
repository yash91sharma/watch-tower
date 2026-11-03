// Shared MSW handlers: default API answers for all tests.
// A test changes an answer for itself with server.use(...).
import { http, HttpResponse, type HttpHandler } from "msw";

export const handlers: HttpHandler[] = [
  // The admin is logged in, so the auth guard opens the app.
  http.get("*/api/auth/state", () => HttpResponse.json({ setup_required: false, logged_in: true })),
  http.get("*/api/containers", () => HttpResponse.json([])),
];
