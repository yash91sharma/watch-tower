// Typed API client (openapi-fetch with the generated types). Same-origin cookies.
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "@/api/schema";

/** A 422 error for one field. */
export interface FieldError {
  field: string;
  message: string;
}

/** An API error: the HTTP status, the WT error detail and the field errors (422). */
export class ApiError extends Error {
  readonly status: number;
  readonly fields: FieldError[];

  constructor(status: number, message: string, fields: FieldError[] = []) {
    super(message);
    this.status = status;
    this.fields = fields;
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
    // WT errors: {error, detail}. The detail is a text, or the field errors for a 422.
    const body = result.error as { error?: string; detail?: unknown } | undefined;
    if (Array.isArray(body?.detail)) {
      throw new ApiError(result.response.status, body.error ?? result.response.statusText, body.detail as FieldError[]);
    }
    const detail = typeof body?.detail === "string" ? body.detail : result.response.statusText;
    throw new ApiError(result.response.status, detail);
  }
  return result.data;
}
