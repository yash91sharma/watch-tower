import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test } from "vitest";

import { containerDetail } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

let saved: { source: string | null; confirmed: boolean }[] = [];

// A fake backend that keeps the release source.
function start(source: string | null, confirmed: boolean) {
  let current = { release_source: source, source_confirmed: confirmed };
  server.use(
    http.get("*/api/containers/:name", () => HttpResponse.json(containerDetail(current))),
    http.put("*/api/containers/:name/release-source", async ({ request }) => {
      const body = (await request.json()) as { source: string | null; confirmed: boolean };
      saved.push(body);
      current = { release_source: body.source, source_confirmed: body.confirmed || body.source === null };
      return HttpResponse.json({ name: "web", ...current });
    }),
  );
  const user = userEvent.setup();
  renderRoute("/containers/web");
  return user;
}

async function section() {
  return within(await screen.findByRole("region", { name: "Release source" }));
}

beforeEach(() => {
  saved = [];
});

test("the form shows the value and not confirmed", async () => {
  start("https://github.com/nginx/nginx", false);

  const form = await section();
  expect(form.getByText("https://github.com/nginx/nginx")).toBeInTheDocument();
  expect(form.getByText("not confirmed")).toBeInTheDocument();
});

test("confirm sends the value, and not confirmed goes", async () => {
  const user = start("nginx/nginx", false);
  const form = await section();

  await user.click(form.getByRole("button", { name: "Confirm" }));

  expect(saved).toEqual([{ source: "nginx/nginx", confirmed: true }]);
  await waitFor(() => {
    expect(form.queryByText("not confirmed")).not.toBeInTheDocument();
  });
  expect(form.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
});

test("edit saves a new value as confirmed", async () => {
  const user = start("nginx/nginx", true);
  const form = await section();

  await user.click(form.getByRole("button", { name: "Edit" }));
  const input = form.getByLabelText("GitHub URL or owner/repo");
  expect(input).toHaveValue("nginx/nginx");
  await user.clear(input);
  await user.type(input, "acme/web");
  await user.click(form.getByRole("button", { name: "Save" }));

  expect(saved).toEqual([{ source: "acme/web", confirmed: true }]);
  expect(await form.findByText("acme/web")).toBeInTheDocument();
});

test("an empty value clears the source", async () => {
  const user = start("nginx/nginx", true);
  const form = await section();

  await user.click(form.getByRole("button", { name: "Edit" }));
  await user.clear(form.getByLabelText("GitHub URL or owner/repo"));
  await user.click(form.getByRole("button", { name: "Save" }));

  expect(saved).toEqual([{ source: null, confirmed: true }]);
  expect(await form.findByText("No release source")).toBeInTheDocument();
});

test("cancel ends the edit with no change", async () => {
  const user = start("nginx/nginx", true);
  const form = await section();

  await user.click(form.getByRole("button", { name: "Edit" }));
  await user.click(form.getByRole("button", { name: "Cancel" }));

  expect(form.getByText("nginx/nginx")).toBeInTheDocument();
  expect(saved).toEqual([]);
});

test("a bad value shows the field error", async () => {
  const user = start("nginx/nginx", true);
  server.use(
    http.put("*/api/containers/:name/release-source", () =>
      HttpResponse.json(
        { error: "Unprocessable Content", detail: [{ field: "source", message: "Give a GitHub URL or owner/repo" }] },
        { status: 422 },
      ),
    ),
  );
  const form = await section();

  await user.click(form.getByRole("button", { name: "Edit" }));
  await user.type(form.getByLabelText("GitHub URL or owner/repo"), "x");
  await user.click(form.getByRole("button", { name: "Save" }));

  expect(await form.findByRole("alert")).toHaveTextContent("source: Give a GitHub URL or owner/repo");
});
