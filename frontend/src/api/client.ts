// Typed API client (openapi-fetch with the generated types). Same-origin cookies.
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "@/api/schema";

/** A 422 error for one field. */
export interface FieldError {
  field: string;
  message: string;
}

/** An API error: the HTTP status, the WT error detail, the field errors (422) and Retry-After (429). */
export class ApiError extends Error {
  readonly status: number;
  readonly fields: FieldError[];
  /** Seconds to wait, from the Retry-After header. */
  readonly retryAfter: number | null;

  constructor(
    status: number,
    message: string,
    { fields = [], retryAfter = null }: { fields?: FieldError[]; retryAfter?: number | null } = {},
  ) {
    super(message);
    this.status = status;
    this.fields = fields;
    this.retryAfter = retryAfter;
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

/** The data of a result (undefined for a 204), or an ApiError. For TanStack Query functions. */
export function unwrap<T>(result: Result<T>): T {
  const { response } = result;
  if (response.ok) return result.data as T;

  // WT errors: {error, detail}. The detail is a text, or the field errors for a 422.
  const body = result.error as { error?: string; detail?: unknown } | undefined;
  const header = response.headers.get("Retry-After");
  const retryAfter = header === null ? null : Number(header);
  if (Array.isArray(body?.detail)) {
    const fields = body.detail as FieldError[];
    throw new ApiError(response.status, body.error ?? response.statusText, { fields, retryAfter });
  }
  const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
  throw new ApiError(response.status, detail, { retryAfter });
}
