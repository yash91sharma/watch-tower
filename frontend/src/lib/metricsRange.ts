// One shared chart range for all charts on all pages. A change in one range select
// changes all charts. The browser keeps the range in localStorage.
import { useSyncExternalStore } from "react";

import type { RangeKey } from "@/api/types";

const storageKey = "wt.metricsRange";
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function read() {
  return localStorage.getItem(storageKey);
}

function save(range: RangeKey) {
  localStorage.setItem(storageKey, range);
  for (const listener of listeners) listener();
}

/** The range and its setter. A kept range that is not in `ranges` (from the API) gives the first range. */
export function useMetricsRange(ranges: { key: RangeKey }[]): [RangeKey, (range: RangeKey) => void] {
  const kept = useSyncExternalStore(subscribe, read);
  const range = ranges.find((item) => item.key === kept)?.key ?? ranges[0]?.key ?? "1h";
  return [range, save];
}
