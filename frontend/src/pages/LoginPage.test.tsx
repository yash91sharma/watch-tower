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

async function logIn(code = "123456") {
  const user = userEvent.setup();
  renderRoute("/login");
  await user.type(await screen.findByLabelText("Password"), "a-long-password");
  await user.type(screen.getByLabelText("TOTP code"), code);
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

test("a value that is not a 6-digit code shows a clear error and sends nothing", async () => {
  // For example the TOTP secret, pasted by mistake.
  await logIn("JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP");

  expect(await screen.findByRole("alert")).toHaveTextContent("Enter the 6-digit code from your authenticator app");
  expect(loginBody).toBeUndefined();
});

test("a code with a space is sent as typed (the backend ignores spaces)", async () => {
  await logIn("123 456");

  expect(await screen.findByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
  expect(loginBody).toEqual({ password: "a-long-password", totp_code: "123 456" });
});

test("a wait of one minute or less says '1 minute'", async () => {
  server.use(
    http.post("*/api/auth/login", () =>
      HttpResponse.json(
        { error: "Too Many Requests", detail: "Too many failed attempts. Try again later." },
        { status: 429, headers: { "Retry-After": "30" } },
      ),
    ),
  );

  await logIn();

  expect(await screen.findByRole("alert")).toHaveTextContent("Too many failed attempts. Try again in 1 minute.");
});

test("a 429 with no Retry-After shows the backend text", async () => {
  server.use(
    http.post("*/api/auth/login", () =>
      HttpResponse.json({ error: "Too Many Requests", detail: "Too many failed attempts. Try again later." }, { status: 429 }),
    ),
  );

  await logIn();

  expect(await screen.findByRole("alert")).toHaveTextContent("Too many failed attempts. Try again later.");
});
