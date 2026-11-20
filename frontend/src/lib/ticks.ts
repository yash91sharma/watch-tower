// The text of the chart axis ticks and legend values, from the unit that the API sends.
// This is display format only: the backend gives the labels of all current values.
import type { Chart } from "@/api/types";

type Unit = Chart["unit"];

const BYTE_UNITS = ["B", "KiB", "MiB", "GiB", "TiB"];

/** A value with 3 significant digits below 10 (0.0412, 2.5), else 1 or 0 decimals (25, 123). */
function short(value: number): string {
  const size = Math.abs(value);
  if (size >= 100) return value.toFixed(0);
  if (size >= 10) return String(Number(value.toFixed(1)));
  return String(Number(value.toPrecision(3)));
}

/** The binary unit (KiB = 1024 B) of a byte value, and the divisor for that unit. */
function byteUnit(value: number): { name: string; divisor: number } {
  let index = 0;
  while (Math.abs(value) >= 1024 ** (index + 1) && index < BYTE_UNITS.length - 1) index += 1;
  return { name: BYTE_UNITS[index] ?? "B", divisor: 1024 ** index };
}

/** The text of one number in its unit, with `text` for the number part. */
function withUnit(value: number, unit: Unit, text: (scaled: number) => string, byteValue = value): string {
  if (unit === "percent") return `${text(value)}%`;
  if (unit === "load") return text(value);
  const { name, divisor } = byteUnit(byteValue);
  return `${text(value / divisor)} ${name}${unit === "bytes_per_second" ? "/s" : ""}`;
}

/** One value, for example in the legend on hover. A small value keeps its digits (0.0412%). */
export function formatTick(value: number, unit: Unit): string {
  return withUnit(value, unit, short);
}

/**
 * The labels of the y-axis ticks. All ticks have the same unit and the same decimals: just
 * enough to tell two ticks apart (0.000%, 0.002%, 0.004% for a small CPU value).
 */
export function formatTicks(ticks: number[], unit: Unit): string[] {
  const largest = Math.max(0, ...ticks.map(Math.abs));
  const { divisor } = unit === "bytes" || unit === "bytes_per_second" ? byteUnit(largest) : { divisor: 1 };
  const steps = ticks.slice(1).map((tick, index) => tick - (ticks[index] ?? 0));
  const step = Math.min(...steps.filter((value) => value > 0)) / divisor;
  if (!Number.isFinite(step)) return ticks.map((tick) => formatTick(tick, unit));
  const scaled = ticks.map((tick) => tick / divisor);
  // The fewest decimals that show each tick exactly (0.025 needs 3). A small tolerance:
  // a tick of 0.1 can be 0.09999999 after the divide.
  let decimals = 0;
  while (decimals < 6 && scaled.some((tick) => Math.abs(Number(tick.toFixed(decimals)) - tick) > step / 1000)) {
    decimals += 1;
  }
  return ticks.map((tick) => withUnit(tick, unit, (value) => value.toFixed(decimals), largest));
}

/** The width (px) of the y axis: enough for the longest tick label. */
export function axisSize(labels: string[] | undefined): number {
  const longest = Math.max(0, ...(labels ?? []).map((label) => label.length));
  return Math.max(48, longest * 7 + 16);
}
