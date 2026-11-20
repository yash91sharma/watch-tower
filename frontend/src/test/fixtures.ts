// Test data in the API shapes.
import type {
  ContainerDetail,
  ContainerOut,
  ContainerUsage,
  GroupUsage,
  History,
  Overview,
  SettingsOut,
  Sparklines,
  VmOut,
} from "@/api/types";

/** A running, healthy container with no update. */
export function container(fields: Partial<ContainerOut> = {}): ContainerOut {
  return {
    name: "web",
    state: "running",
    health: "healthy",
    health_label: "healthy",
    image: "nginx",
    tag: "1.27.0",
    status: "up to date",
    status_label: "up to date",
    latest_version: "1.27.0",
    latest_url: "https://github.com/nginx/nginx/releases/tag/1.27.0",
    severity: null,
    release_source: "nginx/nginx",
    source_confirmed: true,
    ...fields,
  };
}

/** The container detail: no update and no events. */
export function containerDetail(fields: Partial<ContainerDetail> = {}): ContainerDetail {
  return { ...container(), update: null, events: [], ...fields };
}

/** The settings: defaults, ntfy set up, only the ntfy token set. */
export function settingsOut(): SettingsOut {
  return {
    values: {
      check_interval_hours: 24,
      restart_count: 3,
      restart_window_minutes: 10,
      ntfy_url: "https://ntfy.example.com/",
      ntfy_topic: "wt",
      llm_url: null,
      llm_model: null,
      public_url: null,
      metrics_interval_seconds: 10,
    },
    secrets: { github_token: "not set", ntfy_token: "set", llm_api_key: "not set" },
  };
}

/** The current values of a running container. */
export function containerUsage(fields: Partial<ContainerUsage> = {}): ContainerUsage {
  return {
    name: "web",
    state: "running",
    cpu_percent: 9.1,
    cpu_label: "9.1% (1.0 core)",
    mem_used: 1073741824,
    mem_percent: 12.5,
    mem_label: "1.0 / 8.0 GiB",
    net_rx_label: "1.2 KiB/s",
    net_tx_label: "300 B/s",
    disk_read_label: "0 B/s",
    disk_write_label: "4.0 KiB/s",
    ...fields,
  };
}

/** A group with one container. */
export function groupUsage(fields: Partial<GroupUsage> = {}): GroupUsage {
  return {
    project: "site",
    label: "site",
    cpu_percent: 9.1,
    cpu_label: "9.1% (1.0 core)",
    mem_used: 1073741824,
    mem_label: "1.0 GiB",
    containers: [containerUsage()],
    ...fields,
  };
}

/** The current values of the Docker VM. */
export function vmOut(fields: Partial<VmOut> = {}): VmOut {
  return {
    cpu_percent: 25,
    cpu_label: "25% (2.8 cores)",
    cores: 11,
    mem_percent: 40,
    mem_label: "3.2 / 8.0 GiB",
    containers_mem_label: "2.1 GiB",
    swap_percent: 5,
    swap_label: "0.2 / 4.0 GiB",
    disk_percent: 48,
    disk_label: "217.0 / 461.0 GiB",
    disk_read_label: "12.0 KiB/s",
    disk_write_label: "48.0 KiB/s",
    net_rx_label: "1.2 KiB/s",
    net_tx_label: "300 B/s",
    load_label: "0.52 / 0.40 / 0.35",
    uptime_label: "3 d 4 h",
    ...fields,
  };
}

/** The overview: the VM, one group with one container. */
export function overview(fields: Partial<Overview> = {}): Overview {
  return {
    sampled_at: "2026-01-01T00:00:00Z",
    interval_seconds: 10,
    vm: vmOut(),
    counts: { apps: 1, containers: 1, running: 1, apps_label: "1 app", containers_label: "1 running of 1 containers" },
    groups: [groupUsage()],
    ranges: [
      { key: "1h", label: "1 hour" },
      { key: "6h", label: "6 hours" },
      { key: "24h", label: "24 hours" },
      { key: "7d", label: "7 days" },
      { key: "30d", label: "30 days" },
    ],
    ...fields,
  };
}

/** Sparklines of the group "site" and the container "web": 60 slots, values in the last 2. */
export function sparklines(): Sparklines {
  const line = { cpu: [...Array<null>(58).fill(null), 1, 2], mem: [...Array<null>(58).fill(null), 100, 200] };
  return { start: "2026-01-01T00:00:00Z", groups: { site: line }, containers: { web: line } };
}

/** A history with 2 slots and one CPU chart. */
export function history(fields: Partial<History> = {}): History {
  return {
    range: "1h",
    step_seconds: 60,
    times: [1767225600, 1767225660],
    charts: [
      {
        key: "cpu",
        title: "CPU",
        unit: "percent",
        max: 100,
        series: [{ key: "cpu", label: "CPU", values: [1, null] }],
      },
    ],
    ...fields,
  };
}
