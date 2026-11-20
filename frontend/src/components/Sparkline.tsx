// A small line of the last values (for example 60 minutes of CPU), with no axes.
// A null value is a gap. The largest value is at the top, 0 at the bottom.

const WIDTH = 80;
const HEIGHT = 10;

/** The SVG path of the values in a width x height box. */
export function sparklinePath(values: (number | null)[], width: number, height: number): string {
  const max = Math.max(0, ...values.map((value) => value ?? 0));
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  let path = "";
  let gap = true;
  values.forEach((value, index) => {
    if (value === null) {
      gap = true;
      return;
    }
    const x = round(index * step);
    const y = round(max > 0 ? height - (value / max) * height : height);
    path += `${gap ? "M" : "L"}${String(x)},${String(y)}`;
    gap = false;
  });
  return path;
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}

export function Sparkline({ values, label }: { values: (number | null)[]; label: string }) {
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
      preserveAspectRatio="none"
      className="h-5 w-20 shrink-0 overflow-visible text-chart-1"
    >
      <path
        d={sparklinePath(values, WIDTH, HEIGHT)}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
