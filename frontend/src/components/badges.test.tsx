import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { HealthBadge, SeverityBadge, StateLabel, StatusBadge } from "@/components/badges";

test.each([
  ["healthy", "healthy", "success"],
  ["unhealthy", "unhealthy", "destructive"],
  ["starting", "starting", "warning"],
  ["none", "no healthcheck", "outline"],
] as const)("health %s shows the label %s with the %s color", (health, label, variant) => {
  render(<HealthBadge health={health} label={label} />);

  expect(screen.getByText(label)).toHaveAttribute("data-variant", variant);
});

test.each([
  ["critical", "destructive"],
  ["normal", "info"],
] as const)("severity %s has the %s color", (severity, variant) => {
  render(<SeverityBadge severity={severity} />);

  expect(screen.getByText(severity)).toHaveAttribute("data-variant", variant);
});

test("no severity shows no badge", () => {
  const { container } = render(<SeverityBadge severity={null} />);

  expect(container).toBeEmptyDOMElement();
});

test.each([
  ["update", "update available", "info"],
  ["up to date", "up to date", "success"],
  ["error", "error", "destructive"],
  ["no check", "no check", "outline"],
  ["no source", "no source", "outline"],
  ["not checked", "not checked", "outline"],
] as const)("status %s shows the label %s with the %s color", (status, label, variant) => {
  render(<StatusBadge status={status} label={label} />);

  expect(screen.getByText(label)).toHaveAttribute("data-variant", variant);
});

test("the badges show the label text from the API", () => {
  render(
    <>
      <HealthBadge health="none" label="API health text" />
      <StatusBadge status="update" label="API status text" />
    </>,
  );

  expect(screen.getByText("API health text")).toHaveAttribute("data-variant", "outline");
  expect(screen.getByText("API status text")).toHaveAttribute("data-variant", "info");
});

test("a critical update has the destructive color", () => {
  render(<StatusBadge status="update" label="critical update" severity="critical" />);

  expect(screen.getByText("critical update")).toHaveAttribute("data-variant", "destructive");
});

test("a normal update has the info color", () => {
  render(<StatusBadge status="update" label="update available" severity="normal" />);

  expect(screen.getByText("update available")).toHaveAttribute("data-variant", "info");
});

test.each([
  ["running", "success"],
  ["restarting", "warning"],
  ["exited", "destructive"],
  ["dead", "destructive"],
  ["paused", "outline"],
  ["created", "outline"],
])("state %s shows a dot with the %s color", (state, variant) => {
  render(<StateLabel state={state} />);

  expect(screen.getByText(state)).toHaveAttribute("data-variant", variant);
});
