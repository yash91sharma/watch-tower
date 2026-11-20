// The text of the chart axis ticks and legend values, from the unit that the API sends.
// This is display format only: the backend gives the labels of all current values.
import type { Chart } from "@/api/types";


/** Up to 2 decimals, with no trailing zeros (for example 2.5, 3, 1.23). */
function short(value: number, decimals = 2): string {
  return String(Number(value.toFixed(decimals)));
}

/** Binary units (KiB = 1024 B), the same as the backend labels. */
function bytes(value: number): string {
  for (const unit of ["B", "KiB", "MiB", "GiB"]) {
    if (value < 1024) return `${short(value, 1)} ${unit}`;
    value /= 1024;
  }
  return `${short(value, 1)} TiB`;
}

export function formatTick(value: number, unit: Chart["unit"]): string {
  switch (unit) {
    case "percent":
      return `${short(value, 1)}%`;
    case "bytes":
      return bytes(value);
    case "bytes_per_second":
      return `${bytes(value)}/s`;
    case "load":
      return short(value);
  }
}
