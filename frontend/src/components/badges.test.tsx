import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { HealthBadge, SeverityBadge, StatusBadge } from "@/components/badges";

test.each([
  ["healthy", "healthy", "success"],
  ["unhealthy", "unhealthy", "destructive"],
  ["starting", "starting", "warning"],
  ["none", "no healthcheck", "outline"],
] as const)("health %s shows %s with the %s color", (health, text, variant) => {
  render(<HealthBadge health={health} />);

  expect(screen.getByText(text)).toHaveAttribute("data-variant", variant);
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
] as const)("status %s shows %s with the %s color", (status, text, variant) => {
  render(<StatusBadge status={status} />);

  expect(screen.getByText(text)).toHaveAttribute("data-variant", variant);
});
