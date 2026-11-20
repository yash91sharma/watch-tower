import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { DetailList } from "@/components/DetailList";

test("DetailList shows each term with its value, in order", () => {
  const { container } = render(
    <DetailList
      items={[
        { term: "State", value: "running" },
        { term: "Health", value: <strong>healthy</strong> },
      ]}
    />,
  );

  const terms = [...container.querySelectorAll("dt")].map((item) => item.textContent);
  const values = [...container.querySelectorAll("dd")].map((item) => item.textContent);
  expect(terms).toEqual(["State", "Health"]);
  expect(values).toEqual(["running", "healthy"]);
  expect(screen.getByText("healthy").tagName).toBe("STRONG");
});

test("DetailList gives the class names to the list and to a value", () => {
  const { container } = render(
    <DetailList className="gap-y-1" items={[{ term: "Image", value: "nginx", className: "break-all" }]} />,
  );

  expect(container.querySelector("dl")).toHaveClass("grid", "gap-y-1");
  expect(container.querySelector("dl")).not.toHaveClass("gap-y-2");
  expect(screen.getByText("nginx")).toHaveClass("break-all");
});
