import { act, renderHook } from "@testing-library/react";
import { expect, test } from "vitest";

import { useMetricsRange } from "@/lib/metricsRange";
import { overview } from "@/test/fixtures";

const ranges = overview().ranges;

test("the default range is the first one", () => {
  const { result } = renderHook(() => useMetricsRange(ranges));

  expect(result.current[0]).toBe("1h");
});

test("a change goes to all users of the hook and stays after a reload", () => {
  const first = renderHook(() => useMetricsRange(ranges));
  const second = renderHook(() => useMetricsRange(ranges));

  act(() => {
    first.result.current[1]("7d");
  });

  expect(first.result.current[0]).toBe("7d");
  expect(second.result.current[0]).toBe("7d");
  first.unmount();
  second.unmount();
  expect(renderHook(() => useMetricsRange(ranges)).result.current[0]).toBe("7d");
});

test("a kept range that the API does not give is not used", () => {
  localStorage.setItem("wt.metricsRange", "2h");

  const { result } = renderHook(() => useMetricsRange(ranges));

  expect(result.current[0]).toBe("1h");
});

test("with no ranges from the API the range is 1h", () => {
  const { result } = renderHook(() => useMetricsRange([]));

  expect(result.current[0]).toBe("1h");
});
