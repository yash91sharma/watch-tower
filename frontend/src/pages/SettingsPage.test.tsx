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
  const row = (name: string) => {
    const item = secrets.getByText(name).closest("li");
    if (!item) throw new Error(`No row for ${name}`);
    return item;
  };
  expect(within(row("GitHub token")).getByText("not set")).toHaveAttribute("data-variant", "outline");
  expect(within(row("ntfy token")).getByText("set")).toHaveAttribute("data-variant", "success");
  expect(within(row("LLM API key")).getByText("not set")).toHaveAttribute("data-variant", "outline");
  // Each secret tells what WT uses it for.
  expect(row("GitHub token")).toHaveTextContent("GitHub API");
  expect(row("ntfy token")).toHaveTextContent("ntfy");
  expect(row("LLM API key")).toHaveTextContent("summaries");
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
  // The form now has the saved values, so there is nothing to save.
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
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
    metrics_interval_seconds: "10",
  });
});

test("the metrics interval is a select with the values of the API, and a save sends the choice", async () => {
  let body: unknown;
  server.use(
    http.get("*/api/settings", () => HttpResponse.json({ ...settingsOut(), metrics_intervals: [10, 30] })),
    http.put("*/api/settings", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(settingsOut());
    }),
  );
  const user = userEvent.setup();
  renderRoute("/settings");
  const select = await screen.findByLabelText("Metrics interval (seconds)");

  expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual(["10", "30"]);
  expect(select).toHaveValue("10");
  await user.selectOptions(select, "30");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(body).toMatchObject({ metrics_interval_seconds: "30" });
});

test("save shows the backend field errors", async () => {
  server.use(
    http.put("*/api/settings", () =>
      HttpResponse.json(
        {
          error: "Unprocessable Content",
          detail: [
            { field: "check_interval_hours", message: "Give a number of 1 or more" },
            { field: "ntfy_url", message: "The URL must start with http:// or https://" },
          ],
        },
        { status: 422 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderRoute("/settings");
  await user.type(await screen.findByLabelText("Check interval (hours)"), "0");

  await user.click(screen.getByRole("button", { name: "Save" }));

  // The field labels of the form, not the API keys. No HTTP status text.
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Some values are not correct:");
  expect(alert).toHaveTextContent("Check interval (hours): Give a number of 1 or more");
  expect(alert).toHaveTextContent("ntfy URL: The URL must start with http:// or https://");
  expect(alert).not.toHaveTextContent("Unprocessable");
  expect(screen.queryByText("Saved.")).not.toBeInTheDocument();
});

test("send test sends the form values (not saved) and says so", async () => {
  let body: unknown;
  let saved = false;
  server.use(
    http.post("*/api/settings/ntfy-test", async ({ request }) => {
      body = await request.json();
      return new HttpResponse(null, { status: 204 });
    }),
    http.put("*/api/settings", () => {
      saved = true;
      return HttpResponse.json(settingsOut());
    }),
  );
  const user = userEvent.setup();
  renderRoute("/settings");
  const topic = await screen.findByLabelText("ntfy topic");

  await user.clear(topic);
  await user.type(topic, "alerts");
  await user.click(screen.getByRole("button", { name: "Send test notification" }));

  expect(await screen.findByText("Sent. Look for it in ntfy.")).toBeInTheDocument();
  expect(body).toMatchObject({ ntfy_url: "https://ntfy.example.com/", ntfy_topic: "alerts" });
  expect(saved).toBe(false);
});

test("send test shows the backend error", async () => {
  server.use(
    http.post("*/api/settings/ntfy-test", () =>
      HttpResponse.json(
        {
          error: "Bad Gateway",
          detail: "ntfy did not accept the message. Check the URL, the topic and the token.",
        },
        { status: 502 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderRoute("/settings");

  await user.click(await screen.findByRole("button", { name: "Send test notification" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("ntfy did not accept the message.");
  expect(screen.queryByText("Sent. Look for it in ntfy.")).not.toBeInTheDocument();
});

test("a settings load error shows the API error", async () => {
  server.use(
    http.get("*/api/settings", () =>
      HttpResponse.json({ error: "Internal Server Error", detail: "An error occurred. See the WT log." }, { status: 500 }),
    ),
  );
  renderRoute("/settings");

  expect(await screen.findByRole("alert")).toHaveTextContent("An error occurred. See the WT log.");
});

test("Save is off until a value changes, and the sticky bar then says that there are unsaved changes", async () => {
  const user = userEvent.setup();
  renderRoute("/settings");
  const save = await screen.findByRole("button", { name: "Save" });

  expect(save).toBeDisabled();
  expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
  expect(save.closest(".sticky")).not.toBeNull();
  await user.type(screen.getByLabelText("ntfy topic"), "2");

  expect(save).toBeEnabled();
  expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
});

test("Discard puts back the saved values", async () => {
  const user = userEvent.setup();
  renderRoute("/settings");
  const topic = await screen.findByLabelText("ntfy topic");
  await user.type(topic, "2");

  await user.click(screen.getByRole("button", { name: "Discard" }));

  expect(topic).toHaveValue("wt");
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Discard" })).not.toBeInTheDocument();
});

test("a link to another page with unsaved changes asks first", async () => {
  const user = userEvent.setup();
  const { router } = renderRoute("/settings");
  const topic = await screen.findByLabelText("ntfy topic");
  await user.type(topic, "2");
  const apps = within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Apps" });

  await user.click(apps);
  const dialog = await screen.findByRole("alertdialog", { name: "Leave without saving?" });
  await user.click(within(dialog).getByRole("button", { name: "Stay" }));

  expect(router.state.location.pathname).toBe("/settings");
  expect(topic).toHaveValue("wt2");

  await user.click(apps);
  await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Leave" }));

  expect(router.state.location.pathname).toBe("/apps");
});

test("a link to another page with no changes does not ask", async () => {
  const user = userEvent.setup();
  const { router } = renderRoute("/settings");
  await screen.findByLabelText("ntfy topic");

  await user.click(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Apps" }));

  expect(router.state.location.pathname).toBe("/apps");
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});

test("a reload or a tab close with unsaved changes opens the dialog of the browser", async () => {
  const user = userEvent.setup();
  renderRoute("/settings");
  const unload = () => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  };
  await screen.findByLabelText("ntfy topic");
  expect(unload()).toBe(false);

  await user.type(screen.getByLabelText("ntfy topic"), "2");

  expect(unload()).toBe(true);
});
