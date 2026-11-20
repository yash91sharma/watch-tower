import { expect, test } from "vitest";

import { formatTick } from "@/lib/ticks";

test.each([
  [25, "percent", "25%"],
  [2.5, "percent", "2.5%"],
  [0, "bytes", "0 B"],
  [1536, "bytes", "1.5 KiB"],
  [3 * 1024 ** 3, "bytes", "3 GiB"],
  [2048 * 1024 ** 4, "bytes", "2048 TiB"],
  [1.25 * 1024 ** 2, "bytes_per_second", "1.3 MiB/s"],
  [0.5, "load", "0.5"],
  [1.234, "load", "1.23"],
] as const)("%s in %s is %s", (value, unit, label) => {
  expect(formatTick(value, unit)).toBe(label);
});
