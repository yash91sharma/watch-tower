import { QueryClient, QueryClientProvider, queryOptions } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type uPlot from "uplot";
import { expect, test } from "vitest";

import type { RangeKey } from "@/api/types";
import { HistoryCharts, MetricChart } from "@/components/MetricChart";
import { history, overview } from "@/test/fixtures";
import { plots, resizeCallbacks } from "@/test/uplot";

const ranges = overview().ranges;
const [cpu] = history().charts;
// The axis and legend callbacks do not read the plot.
const noPlot = {} as unknown as uPlot;

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
  expect(range(noPlot, 2, 300)).toEqual([0, 100]);
  expect(range(noPlot, 0, 4)).toEqual([0, 4.4]);
  expect(range(noPlot, 0, 0)).toEqual([0, 1]);
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
  expect(value(noPlot, 25)).toBe("25%");
  expect(value(noPlot, null)).toBe("-");
  const ticks = plots[0]?.options.axes?.[1]?.values as (u: uPlot, t: number[]) => string[];
  expect(ticks(noPlot, [0, 50])).toEqual(["0%", "50%"]);
  // A small CPU value: the ticks keep the digits that make them different.
  expect(ticks(noPlot, [0, 0.002, 0.004])).toEqual(["0.000%", "0.002%", "0.004%"]);
  const size = plots[0]?.options.axes?.[1]?.size as (u: uPlot, labels: string[]) => number;
  expect(size(noPlot, ["0.000%", "0.002%"])).toBe(58);
});

test("a byte chart has binary tick steps, so that the ticks are round in KiB, MiB and GiB", () => {
  if (!cpu) throw new Error("no chart");
  render(
    <>
      <MetricChart chart={{ ...cpu, key: "memory", title: "Memory", unit: "bytes", max: null }} times={[1, 2]} ranges={ranges} />
      <MetricChart chart={cpu} times={[1, 2]} ranges={ranges} />
    </>,
  );

  const incrs = plots[0]?.options.axes?.[1]?.incrs as number[];
  // Not 2,000,000 B (1.907 MiB) and not 0.5 B.
  expect(incrs).toContain(512 * 1024);
  expect(incrs).toContain(2 ** 30);
  expect(incrs.every((step) => Number.isInteger(Math.log2(step)) && step >= 1)).toBe(true);
  // A percent chart keeps the uPlot steps (10, 20, 25, 50).
  expect(plots[1]?.options.axes?.[1]?.incrs).toBeUndefined();
});

test("a range with no values shows the text of the API on the chart", () => {
  if (!cpu) throw new Error("no chart");
  const { rerender } = render(<MetricChart chart={cpu} times={[1, 2]} ranges={ranges} emptyLabel={null} />);
  expect(screen.queryByText("No values in this range.")).not.toBeInTheDocument();

  rerender(<MetricChart chart={cpu} times={[1, 2]} ranges={ranges} emptyLabel="No values in this range." />);

  expect(screen.getByText("No values in this range.")).toBeInTheDocument();
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

  resizeCallbacks[0]?.();

  expect(plots[0]?.sizes).toEqual([{ width: 0, height: 160 }]);
});

test("a chart with no max scales the y axis to its values", () => {
  if (!cpu) throw new Error("no chart");
  render(<MetricChart chart={{ ...cpu, max: null }} times={[1, 2]} ranges={ranges} />);

  const range = plots[0]?.options.scales?.y?.range as (u: uPlot, min: number, max: number) => [number, number];
  expect(range(noPlot, 0, 1000)).toEqual([0, 1100]);
});

test("the history charts get the history of the shared range and show each chart, with the times and the empty label", async () => {
  if (!cpu) throw new Error("no chart");
  const memory = { ...cpu, key: "memory", title: "Memory", unit: "bytes" as const, max: null };
  localStorage.setItem("wt.metricsRange", "7d");
  const asked: RangeKey[] = [];
  const query = (range: RangeKey) =>
    queryOptions({
      queryKey: ["history", range],
      queryFn: () => {
        asked.push(range);
        return history({ charts: [cpu, memory], empty_label: "No values." });
      },
    });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <HistoryCharts ranges={ranges} query={query} />
    </QueryClientProvider>,
  );

  expect(screen.getByText("Loading charts…")).toBeInTheDocument();
  expect((await screen.findAllByRole("heading")).map((item) => item.textContent)).toEqual(["CPU", "Memory"]);
  expect(asked).toEqual(["7d"]);
  expect(screen.getAllByText("No values.")).toHaveLength(2);
  expect(plots.map((plot) => plot.data[0])).toEqual([history().times, history().times]);
});
