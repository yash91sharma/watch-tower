import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

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
  expect(error).toMatchObject({ status: 404, message: "No such thing" });
});
