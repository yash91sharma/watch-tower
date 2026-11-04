import { expect, test } from "vitest";

import { cn, plural } from "@/lib/utils";

test("cn joins classes and skips false values", () => {
  expect(cn("a", false, "b")).toBe("a b");
});

test("cn lets a later Tailwind class override an earlier one", () => {
  expect(cn("p-2", "p-4")).toBe("p-4");
});

test("plural gives the count with the matching word", () => {
  expect(plural(1, "container", "containers")).toBe("1 container");
  expect(plural(0, "container", "containers")).toBe("0 containers");
  expect(plural(3, "container", "containers")).toBe("3 containers");
});
