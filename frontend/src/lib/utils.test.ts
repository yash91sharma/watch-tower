import { expect, test } from "vitest";

import { cn } from "@/lib/utils";

test("cn joins classes and skips false values", () => {
  expect(cn("a", false, "b")).toBe("a b");
});

test("cn lets a later Tailwind class override an earlier one", () => {
  expect(cn("p-2", "p-4")).toBe("p-4");
});
