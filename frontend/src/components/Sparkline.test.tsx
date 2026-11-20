import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Sparkline, sparklinePath } from "@/components/Sparkline";

test("the path goes from the first slot to the last, scaled to the largest value", () => {
  // 3 slots in a 100 x 10 box: x = 0, 50, 100. The largest value (4) is at the top.
  expect(sparklinePath([0, 2, 4], 100, 10)).toBe("M0,10L50,5L100,0");
});

test("one value is a point at the left", () => {
  expect(sparklinePath([5], 80, 10)).toBe("M0,0");
});

test("a null value makes a gap", () => {
  expect(sparklinePath([1, null, 1, 1], 30, 10)).toBe("M0,0M20,0L30,0");
});

test("all null or all zero values give a flat line or no line", () => {
  expect(sparklinePath([null, null], 10, 10)).toBe("");
  expect(sparklinePath([0, 0], 10, 10)).toBe("M0,10L10,10");
});

test("the sparkline is an image with a label", () => {
  render(<Sparkline values={[1, 2]} label="CPU of web, last hour" />);

  const image = screen.getByRole("img", { name: "CPU of web, last hour" });
  expect(image.querySelector("path")).toHaveAttribute("d", "M0,5L80,0");
});
