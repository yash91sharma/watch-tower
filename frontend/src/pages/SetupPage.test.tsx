import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test } from "vitest";

import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

const TOKEN = "setup-token";
const SECRET = "JBSWY3DPEHPK3PXP";
const PASSWORD = "a-long-password";
const CODE = "123456";

let finishBody: unknown;

// A fake backend: right token and code only. Setup finish logs the admin in.
beforeEach(() => {
  let setUp = false;
  finishBody = undefined;
  server.use(
    http.get("*/api/auth/state", () => HttpResponse.json({ setup_required: !setUp, logged_in: setUp })),
    http.post("*/api/auth/setup/begin", async ({ request }) => {
      const body = (await request.json()) as { token: string };
      if (body.token !== TOKEN) {
        return HttpResponse.json({ error: "Forbidden", detail: "The setup token is not correct" }, { status: 403 });
      }
      return HttpResponse.json({ totp_secret: SECRET, otpauth_uri: "otpauth://totp/x", qr_svg: "<svg></svg>" });
    }),
    http.post("*/api/auth/setup/finish", async ({ request }) => {
      finishBody = await request.json();
      if ((finishBody as { totp_code: string }).totp_code !== CODE) {
        return HttpResponse.json({ error: "Bad Request", detail: "The TOTP code is not correct" }, { status: 400 });
      }
      setUp = true;
      return HttpResponse.json({ setup_required: false, logged_in: true });
    }),
  );
});

async function enterToken(token: string) {
  const user = userEvent.setup();
  renderRoute("/setup");
  await user.type(await screen.findByLabelText("Setup token"), token);
  await user.click(screen.getByRole("button", { name: "Next" }));
  return user;
}

async function finish(user: ReturnType<typeof userEvent.setup>, password2: string, code: string) {
  await user.type(await screen.findByLabelText("Password"), PASSWORD);
  await user.type(screen.getByLabelText("Password again"), password2);
  await user.type(screen.getByLabelText("TOTP code"), code);
  await user.click(screen.getByRole("button", { name: "Set up" }));
}

test("the full setup opens the app", async () => {
  const user = await enterToken(TOKEN);

  const qr = await screen.findByRole("img", { name: "QR code for the authenticator app" });
  expect(qr).toHaveAttribute("src", `data:image/svg+xml,${encodeURIComponent("<svg></svg>")}`);
  expect(screen.getByText(SECRET)).toBeInTheDocument();

  await finish(user, PASSWORD, CODE);

  expect(await screen.findByRole("heading", { level: 1, name: "Containers" })).toBeInTheDocument();
  expect(finishBody).toEqual({ token: TOKEN, password: PASSWORD, totp_code: CODE });
});

test("a wrong token shows the backend error", async () => {
  await enterToken("wrong");

  expect(await screen.findByRole("alert")).toHaveTextContent("The setup token is not correct");
  expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
});

test("passwords that do not match show an error and send nothing", async () => {
  const user = await enterToken(TOKEN);

  await finish(user, "another-password", CODE);

  expect(await screen.findByRole("alert")).toHaveTextContent("The two passwords are not the same");
  expect(finishBody).toBeUndefined();
});

test("a wrong code shows the backend error", async () => {
  const user = await enterToken(TOKEN);

  await finish(user, PASSWORD, "000000");

  expect(await screen.findByRole("alert")).toHaveTextContent("The TOTP code is not correct");
  expect(screen.getByRole("heading", { level: 1, name: "Set up Watch Tower" })).toBeInTheDocument();
});

test("a field error shows the field and the message", async () => {
  server.use(
    http.post("*/api/auth/setup/finish", () =>
      HttpResponse.json(
        {
          error: "Unprocessable Content",
          detail: [{ field: "password", message: "String should have at least 12 characters" }],
        },
        { status: 422 },
      ),
    ),
  );
  const user = await enterToken(TOKEN);

  await finish(user, PASSWORD, CODE);

  expect(await screen.findByRole("alert")).toHaveTextContent("password: String should have at least 12 characters");
});

test("a value that is not a 6-digit code shows a clear error and sends nothing", async () => {
  const user = await enterToken(TOKEN);

  await finish(user, PASSWORD, SECRET);

  expect(await screen.findByRole("alert")).toHaveTextContent("Enter the 6-digit code from your authenticator app");
  expect(finishBody).toBeUndefined();
});
