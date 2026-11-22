// Times come from the API in UTC. The UI shows them in the browser time zone.

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

// The UI text is English, so the relative text is English too.
const relative = new Intl.RelativeTimeFormat("en", { numeric: "always" });
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** How long ago the time was, for example "5 minutes ago". After 7 days, the date. */
export function formatAgo(iso: string, now: number): string {
  const age = now - Date.parse(iso);
  if (age < MINUTE) return "just now";
  if (age < HOUR) return relative.format(-Math.floor(age / MINUTE), "minute");
  if (age < DAY) return relative.format(-Math.floor(age / HOUR), "hour");
  if (age < 7 * DAY) return relative.format(-Math.floor(age / DAY), "day");
  return formatTime(iso);
}
