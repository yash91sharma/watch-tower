import { expect, test } from "vitest";

import { axisSize, formatTick, formatTicks } from "@/lib/ticks";

// A single value (the legend on hover): 3 significant digits below 10, so a small CPU % is not 0.
test.each([
  [25, "percent", "25%"],
  [2.5, "percent", "2.5%"],
  [0.04123, "percent", "0.0412%"],
  [0, "percent", "0%"],
  [0, "bytes", "0 B"],
  [1536, "bytes", "1.5 KiB"],
  [3 * 1024 ** 3, "bytes", "3 GiB"],
  [2048 * 1024 ** 4, "bytes", "2048 TiB"],
  [1.25 * 1024 ** 2, "bytes_per_second", "1.25 MiB/s"],
  [123.456, "bytes", "123 B"],
  [0.5, "load", "0.5"],
  [1.234, "load", "1.23"],
] as const)("value %s in %s is %s", (value, unit, label) => {
  expect(formatTick(value, unit)).toBe(label);
});

// The axis ticks: all ticks have the same decimals, enough to tell two ticks apart.
test.each([
  [[0, 0.002, 0.004], "percent", ["0.000%", "0.002%", "0.004%"]],
  [[0, 0.0020000000000000018, 0.004], "percent", ["0.000%", "0.002%", "0.004%"]],
  [[0, 0.5, 1], "percent", ["0.0%", "0.5%", "1.0%"]],
  [[0, 0.1, 0.2], "percent", ["0.0%", "0.1%", "0.2%"]],
  [[0, 25, 50], "percent", ["0%", "25%", "50%"]],
  [[0, 0.005, 0.01], "load", ["0.000", "0.005", "0.010"]],
  [[0, 512 * 1024, 1024 * 1024], "bytes", ["0.0 MiB", "0.5 MiB", "1.0 MiB"]],
  [[0, 0.5, 1], "bytes_per_second", ["0.0 B/s", "0.5 B/s", "1.0 B/s"]],
  [[0, 500, 1000], "bytes", ["0 B", "500 B", "1000 B"]],
  [[0, 50 * 1024, 100 * 1024], "bytes", ["0 KiB", "50 KiB", "100 KiB"]],
  [[5], "percent", ["5%"]],
  [[], "percent", []],
] as const)("ticks %j in %s are %j", (ticks, unit, labels) => {
  expect(formatTicks([...ticks], unit)).toEqual(labels);
});

test("the axis is wide enough for the longest tick label", () => {
  expect(axisSize(["0.000%", "0.0035%"])).toBeGreaterThan(axisSize(["0%", "50%"]));
  expect(axisSize(["0%"])).toBe(48);
  expect(axisSize(undefined)).toBe(48);
});
