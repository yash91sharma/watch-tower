// Smoke test: makes sure that the dev container runs Vitest.
import { expect, test } from "vitest";

test("node runs", () => {
  expect(process.versions.node.split(".")[0]).toBe("24");
});
