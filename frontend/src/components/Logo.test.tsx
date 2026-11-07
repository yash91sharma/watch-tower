import { render } from "@testing-library/react";
import { expect, test } from "vitest";

import { Logo } from "@/components/Logo";

test("the logo is pixel art with a still picture and 8 frames of the turning light, 0.5 s each", () => {
  const { container } = render(<Logo />);
  const svg = container.querySelector("svg");

  expect(svg).toHaveAttribute("aria-hidden", "true");
  expect(svg).toHaveAttribute("shape-rendering", "crispEdges");
  expect(container.querySelectorAll(".wt-logo-still")).toHaveLength(1);
  const frames = Array.from(container.querySelectorAll<SVGGElement>(".wt-logo-frame"));
  expect(frames.map((frame) => frame.style.animationDelay)).toEqual(["0s", "0.5s", "1s", "1.5s", "2s", "2.5s", "3s", "3.5s"]);
});
