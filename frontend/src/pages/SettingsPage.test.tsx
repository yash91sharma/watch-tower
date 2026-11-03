import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { settingsOut } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { server } from "@/test/server";

test("the form shows the values", async () => {
  renderRoute("/settings");

  expect(await screen.findByLabelText("Check interval (hours)")).toHaveValue("24");
  expect(screen.getByLabelText("Restart loop: restarts")).toHaveValue("3");
  expect(screen.getByLabelText("Restart loop: window (minutes)")).toHaveValue("10");
  expect(screen.getByLabelText("ntfy URL")).toHaveValue("https://ntfy.example.com/");
  expect(screen.getByLabelText("ntfy topic")).toHaveValue("wt");
  expect(screen.getByLabelText("LLM URL")).toHaveValue("");
  expect(screen.getByLabelText("LLM model")).toHaveValue("");
  expect(screen.getByLabelText("WT URL (for links in notifications)")).toHaveValue("");
});

test("each secret shows as set or not set", async () => {
  renderRoute("/settings");

  const secrets = within(await screen.findByRole("region", { name: "Secrets" }));
  expect(secrets.getByText("GitHub token").nextSibling).toHaveTextContent("not set");
  expect(secrets.getByText("ntfy token").nextSibling).toHaveTextContent("set");
  expect(secrets.getByText("LLM API key").nextSibling).toHaveTextContent("not set");
  expect(secrets.queryByRole("textbox")).not.toBeInTheDocument();
});

test("save sends the values and says so", async () => {
  let body: unknown;
  server.use(
    http.put("*/api/settings", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(settingsOut());
    }),
  );
  const user = userEvent.setup();
  renderRoute("/settings");
  const interval = await screen.findByLabelText("Check interval (hours)");

  await user.clear(interval);
  await user.type(interval, "12");
  await user.type(screen.getByLabelText("LLM model"), "llama3");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  // The backend validates and converts the values.
  expect(body).toEqual({
    check_interval_hours: "12",
    restart_count: "3",
    restart_window_minutes: "10",
    ntfy_url: "https://ntfy.example.com/",
    ntfy_topic: "wt",
    llm_url: "",
    llm_model: "llama3",
    public_url: "",
  });
});

test("save shows the backend field errors", async () => {
  server.use(
    http.put("*/api/settings", () =>
      HttpResponse.json(
        {
          error: "Unprocessable Content",
          detail: [
            { field: "check_interval_hours", message: "Input should be greater than or equal to 1" },
            { field: "ntfy_url", message: "URL scheme should be 'http' or 'https'" },
          ],
        },
        { status: 422 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderRoute("/settings");

  await user.click(await screen.findByRole("button", { name: "Save" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("check_interval_hours: Input should be greater than or equal to 1");
  expect(alert).toHaveTextContent("ntfy_url: URL scheme should be 'http' or 'https'");
  expect(screen.queryByText("Saved.")).not.toBeInTheDocument();
});
