import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type uPlot from "uplot";
import { beforeEach, expect, test, vi } from "vitest";

import { MetricChart } from "@/components/MetricChart";
import { history, overview } from "@/test/fixtures";

// jsdom has no canvas. The fake keeps the options and the data of each chart.
const plots = vi.hoisted(
  () => [] as { options: uPlot.Options; data: uPlot.AlignedData; destroyed: boolean; sizes: unknown[] }[],
);
// The resize callback of the last ResizeObserver.
let resize: () => void = () => undefined;
vi.mock("uplot", () => ({
  default: class {
    private plot: (typeof plots)[number];
    constructor(options: uPlot.Options, data: uPlot.AlignedData) {
      this.plot = { options, data, destroyed: false, sizes: [] };
      plots.push(this.plot);
    }
    setSize(size: unknown) {
      this.plot.sizes.push(size);
    }
    destroy() {
      this.plot.destroyed = true;
    }
  },
}));

beforeEach(() => {
  plots.length = 0;
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(callback: () => void) {
        resize = callback;
      }
      observe = vi.fn();
      disconnect = vi.fn();
    },
  );
});

const ranges = overview().ranges;
const [cpu] = history().charts;

test("the chart has its title, the series labels and the data of the API", () => {
  if (!cpu) throw new Error("no chart");
  render(<MetricChart chart={cpu} times={[1, 2]} ranges={ranges} />);

  expect(screen.getByRole("heading", { name: "CPU" })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "CPU chart" })).toBeInTheDocument();
  const [plot] = plots;
  expect(plot?.data).toEqual([
    [1, 2],
    [1, null],
  ]);
  expect(plot?.options.series.map((series) => series.label)).toEqual([undefined, "CPU"]);
});

test("the y axis stops at the max of the chart and starts at 0", () => {
  if (!cpu) throw new Error("no chart");
  render(<MetricChart chart={cpu} times={[1, 2]} ranges={ranges} />);

  const range = plots[0]?.options.scales?.y?.range as (u: uPlot, min: number, max: number) => [number, number];
  expect(range({} as uPlot, 2, 300)).toEqual([0, 100]);
  expect(range({} as uPlot, 0, 4)).toEqual([0, 4.4]);
  expect(range({} as uPlot, 0, 0)).toEqual([0, 1]);
});

test("a range change in one chart changes the select of all charts", async () => {
  if (!cpu) throw new Error("no chart");
  render(
    <>
      <MetricChart chart={cpu} times={[1, 2]} ranges={ranges} />
      <MetricChart chart={{ ...cpu, key: "memory", title: "Memory", max: null }} times={[1, 2]} ranges={ranges} />
    </>,
  );
  const [first, second] = screen.getAllByRole("combobox", { name: "Range" });
  if (!first || !second) throw new Error("no select");

  await userEvent.selectOptions(first, "7 days");

  expect(first).toHaveValue("7d");
  expect(second).toHaveValue("7d");
});

test("the legend values use the unit of the chart", () => {
  if (!cpu) throw new Error("no chart");
  render(<MetricChart chart={cpu} times={[1, 2]} ranges={ranges} />);

  const value = plots[0]?.options.series[1]?.value as (u: uPlot, v: number | null) => string;
  expect(value({} as uPlot, 25)).toBe("25%");
  expect(value({} as uPlot, null)).toBe("-");
  const ticks = plots[0]?.options.axes?.[1]?.values as (u: uPlot, t: number[]) => string[];
  expect(ticks({} as uPlot, [0, 50])).toEqual(["0%", "50%"]);
});

test("a new chart replaces the old one", () => {
  if (!cpu) throw new Error("no chart");
  const { rerender, unmount } = render(<MetricChart chart={cpu} times={[1, 2]} ranges={ranges} />);

  rerender(<MetricChart chart={cpu} times={[2, 3]} ranges={ranges} />);
  unmount();

  expect(plots.map((plot) => plot.destroyed)).toEqual([true, true]);
});

test("a resize of the box sets the chart size", () => {
  if (!cpu) throw new Error("no chart");
  render(<MetricChart chart={cpu} times={[1, 2]} ranges={ranges} />);

  resize();

  expect(plots[0]?.sizes).toEqual([{ width: 0, height: 160 }]);
});
