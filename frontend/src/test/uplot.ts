// Fake uPlot (jsdom has no canvas) and ResizeObserver. setup.ts installs both for all tests.
// The fake keeps the options, the data and the sizes of each chart, so tests can check them.
import type uPlot from "uplot";

export interface FakePlot {
  options: uPlot.Options;
  data: uPlot.AlignedData;
  destroyed: boolean;
  sizes: unknown[];
}

export const plots: FakePlot[] = [];

export default class FakeUPlot {
  private plot: FakePlot;
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
}

/** The callbacks of the ResizeObserver fakes. A test calls them to send a resize. */
export const resizeCallbacks: (() => void)[] = [];

export class FakeResizeObserver {
  constructor(callback: () => void) {
    resizeCallbacks.push(callback);
  }
  observe() {
    return undefined;
  }
  unobserve() {
    return undefined;
  }
  disconnect() {
    return undefined;
  }
}
