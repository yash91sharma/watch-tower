import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test } from "vitest";

import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

let loggedIn = false;
let loginBody: unknown;

// A fake backend: login always works, logout always works.
beforeEach(() => {
  loggedIn = false;
  loginBody = undefined;
  server.use(
    http.get("*/api/auth/state", () => HttpResponse.json({ setup_required: false, logged_in: loggedIn })),
    http.post("*/api/auth/login", async ({ request }) => {
      loginBody = await request.json();
      loggedIn = true;
      return HttpResponse.json({ setup_required: false, logged_in: true });
    }),
    http.post("*/api/auth/logout", () => {
      loggedIn = false;
      return new HttpResponse(null, { status: 204 });
    }),
  );
});

async function logIn() {
  const user = userEvent.setup();
  renderRoute("/login");
  await user.type(await screen.findByLabelText("Password"), "a-long-password");
  await user.type(screen.getByLabelText("TOTP code"), "123456");
  await user.click(screen.getByRole("button", { name: "Log in" }));
  return user;
}

test("a good login opens the app", async () => {
  await logIn();

  expect(await screen.findByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
  expect(loginBody).toEqual({ password: "a-long-password", totp_code: "123456" });
});

test("a failed login shows the backend error", async () => {
  server.use(
    http.post("*/api/auth/login", () =>
      HttpResponse.json(
        { error: "Unauthorized", detail: "The password or the TOTP code is not correct" },
        { status: 401 },
      ),
    ),
  );

  await logIn();

  expect(await screen.findByRole("alert")).toHaveTextContent("The password or the TOTP code is not correct");
  expect(screen.getByRole("heading", { level: 1, name: "Log in" })).toBeInTheDocument();
});

test("after the login limit, the page shows the wait time", async () => {
  server.use(
    http.post("*/api/auth/login", () =>
      HttpResponse.json(
        { error: "Too Many Requests", detail: "Too many failed attempts. Try again later." },
        { status: 429, headers: { "Retry-After": "841" } },
      ),
    ),
  );

  await logIn();

  expect(await screen.findByRole("alert")).toHaveTextContent("Too many failed attempts. Try again in 15 minutes.");
});

test("log out calls logout and opens /login", async () => {
  const user = await logIn();
  await screen.findByRole("heading", { level: 1, name: "Containers" });

  await user.click(screen.getByRole("button", { name: "Log out" }));

  expect(await screen.findByRole("heading", { level: 1, name: "Log in" })).toBeInTheDocument();
  expect(loggedIn).toBe(false);
});
