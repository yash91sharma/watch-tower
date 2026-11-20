// A time chart of the API (one chart of a history response), drawn with uPlot (canvas).
// The range select uses the shared range, so a change here changes all charts.
// The legend under the chart shows the series labels and, on hover, the values.
// The colors come from the CSS variables when WT draws the chart. The page draws the
// charts again at each new minute, so a change of the light or dark theme shows then.
import { useEffect, useId, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

import type { Chart, RangeKey } from "@/api/types";
import { useMetricsRange } from "@/lib/metricsRange";
import { formatTick } from "@/lib/ticks";

const HEIGHT = 160;
// The validated series colors (index.css: --series-1 to --series-3). No chart has more.
const SERIES_COLORS = 3;

function cssColor(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function options(chart: Chart, width: number): uPlot.Options {
  const axis = { stroke: cssColor("--muted-foreground"), grid: { stroke: cssColor("--border"), width: 1 }, ticks: { show: false } };
  return {
    width,
    height: HEIGHT,
    series: [
      {},
      ...chart.series.map((series, index) => ({
        label: series.label,
        stroke: cssColor(`--series-${String((index % SERIES_COLORS) + 1)}`),
        width: 2,
        points: { show: false },
        value: (_: uPlot, value: number | null) => (value === null ? "-" : formatTick(value, chart.unit)),
      })),
    ],
    axes: [axis, { ...axis, size: 64, values: (_: uPlot, ticks: number[]) => ticks.map((tick) => formatTick(tick, chart.unit)) }],
    scales: {
      // From 0. The top is a bit above the largest value, but not above the max of the chart.
      y: {
        range: (_: uPlot, _min: number, max: number): uPlot.Range.MinMax => [
          0,
          Math.min(chart.max ?? Infinity, max > 0 ? Number((max * 1.1).toPrecision(6)) : 1),
        ],
      },
    },
  };
}

export function MetricChart({
  chart,
  times,
  ranges,
}: {
  chart: Chart;
  times: number[];
  ranges: { key: RangeKey; label: string }[];
}) {
  const [range, setRange] = useMetricsRange(ranges);
  const box = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const data: uPlot.AlignedData = [times, ...chart.series.map((series) => series.values)];
    const plot = new uPlot(options(chart, element.clientWidth), data, element);
    const observer = new ResizeObserver(() => {
      plot.setSize({ width: element.clientWidth, height: HEIGHT });
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      plot.destroy();
    };
  }, [chart, times]);

  return (
    <section aria-labelledby={titleId} className="min-w-0 rounded-xl border bg-card p-3 shadow-xs">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 id={titleId} className="text-sm font-medium">
          {chart.title}
        </h3>
        <select
          aria-label="Range"
          value={range}
          onChange={(event) => {
            setRange(event.target.value as RangeKey);
          }}
          className="rounded-md border bg-background px-1 py-0.5 text-xs"
        >
          {ranges.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <div ref={box} role="img" aria-label={`${chart.title} chart`} className="text-xs" />
    </section>
  );
}
