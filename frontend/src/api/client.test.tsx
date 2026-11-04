import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";

import { api, ApiError, unwrap } from "@/api/client";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

const unauthorized = () => HttpResponse.json({ error: "Unauthorized", detail: "Log in first" }, { status: 401 });

test("a 401 opens /login", async () => {
  server.use(http.get("*/api/containers", unauthorized));
  const { router } = renderRoute("/settings");
  await screen.findByRole("heading", { level: 1, name: "Settings" });
  // The session expired: the auth guard must get the new state, not use the old one.
  server.use(http.get("*/api/auth/state", () => HttpResponse.json({ setup_required: false, logged_in: false })));
  const paths: string[] = [];
  router.subscribe((state) => paths.push(state.location.pathname));

  await api.GET("/api/containers");

  expect(await screen.findByRole("heading", { level: 1, name: "Log in" })).toBeInTheDocument();
  expect(paths).not.toContain("/");
  expect(router.state.location.pathname).toBe("/login");
});

test("a 401 from an auth route does not open /login", async () => {
  server.use(http.post("*/api/auth/login", unauthorized));
  const { router } = renderRoute("/settings");

  await api.POST("/api/auth/login", { body: { password: "x", totp_code: "1" } });

  expect(router.state.location.pathname).toBe("/settings");
});

test("the client sends same-origin cookies", async () => {
  let credentials: RequestCredentials | undefined;
  server.use(
    http.get("*/api/health", ({ request }) => {
      credentials = request.credentials;
      return HttpResponse.json({ status: "ok" });
    }),
  );

  await api.GET("/api/health");

  expect(credentials).toBe("same-origin");
});

test("unwrap gives the data", async () => {
  server.use(http.get("*/api/health", () => HttpResponse.json({ status: "ok" })));

  expect(unwrap(await api.GET("/api/health"))).toEqual({ status: "ok" });
});

test("unwrap throws an ApiError with the status and the detail", async () => {
  server.use(
    http.get("*/api/settings", () =>
      HttpResponse.json({ error: "Not Found", detail: "No such thing" }, { status: 404 }),
    ),
  );

  const error = await api.GET("/api/settings").then(unwrap).catch((caught: unknown) => caught);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status: 404, message: "No such thing", fields: [] });
});

test("unwrap gives the Retry-After seconds", async () => {
  server.use(
    http.post("*/api/auth/login", () =>
      HttpResponse.json(
        { error: "Too Many Requests", detail: "Too many failed attempts. Try again later." },
        { status: 429, headers: { "Retry-After": "120" } },
      ),
    ),
  );

  const error = await api
    .POST("/api/auth/login", { body: { password: "x", totp_code: "1" } })
    .then(unwrap)
    .catch((caught: unknown) => caught);

  expect(error).toMatchObject({ status: 429, retryAfter: 120 });
});

test("unwrap gives the field errors of a 422", async () => {
  const fields = [{ field: "password", message: "String should have at least 12 characters" }];
  server.use(
    http.get("*/api/settings", () =>
      HttpResponse.json({ error: "Unprocessable Content", detail: fields }, { status: 422 }),
    ),
  );

  const error = await api.GET("/api/settings").then(unwrap).catch((caught: unknown) => caught);

  expect(error).toMatchObject({ status: 422, message: "Unprocessable Content", fields });
});

test("unwrap of an error with no WT body gives the status text", async () => {
  server.use(http.get("*/api/settings", () => new HttpResponse("Bad Gateway", { status: 502, statusText: "Bad Gateway" })));

  const error = await api.GET("/api/settings").then(unwrap).catch((caught: unknown) => caught);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status: 502, message: "Bad Gateway", fields: [], retryAfter: null });
});

test("unwrap of a 422 with no error name gives the status text", async () => {
  const fields = [{ field: "tail", message: "Input should be a valid integer" }];
  server.use(
    http.get("*/api/settings", () =>
      HttpResponse.json({ detail: fields }, { status: 422, statusText: "Unprocessable Content" }),
    ),
  );

  const error = await api.GET("/api/settings").then(unwrap).catch((caught: unknown) => caught);

  expect(error).toMatchObject({ status: 422, message: "Unprocessable Content", fields });
});

test("before the app sets a 401 handler, a 401 does nothing", async () => {
  vi.resetModules();
  const fresh = await import("@/api/client");
  server.use(http.get("*/api/containers", unauthorized));

  const result = await fresh.api.GET("/api/containers");

  expect(result.response.status).toBe(401);
});
