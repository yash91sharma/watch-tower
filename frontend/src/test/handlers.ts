// Shared MSW handlers: default API answers for all tests.
// A test changes an answer for itself with server.use(...).
import type { HttpHandler } from "msw";

export const handlers: HttpHandler[] = [];
