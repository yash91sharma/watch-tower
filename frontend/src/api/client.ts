// Typed API client (openapi-fetch with the generated types). Same-origin cookies.
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "@/api/schema";

/** An API error: the HTTP status and the WT error detail. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let unauthorized: () => void = () => undefined;

/** The app sets what a 401 does (open /login). */
export function onUnauthorized(handler: () => void) {
  unauthorized = handler;
}

const loginOn401: Middleware = {
  onResponse({ request, response }) {
    // A failed login is also a 401. Only other routes open /login.
    if (response.status === 401 && !new URL(request.url).pathname.startsWith("/api/auth/")) {
      unauthorized();
    }
  },
};

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // Look up fetch at call time, so that test tools (MSW) can replace it.
  fetch: (request) => globalThis.fetch(request),
});
api.use(loginOn401);

interface Result<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** The data of a result, or an ApiError. For TanStack Query query functions. */
export function unwrap<T>(result: Result<T>): T {
  if (result.error !== undefined || result.data === undefined) {
    const body = result.error as { detail?: unknown } | undefined;
    const detail = typeof body?.detail === "string" ? body.detail : result.response.statusText;
    throw new ApiError(result.response.status, detail);
  }
  return result.data;
}
