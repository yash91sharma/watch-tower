// Test data in the API shapes.
import type { ContainerDetail, ContainerOut, SettingsOut } from "@/api/types";

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
    },
    secrets: { github_token: "not set", ntfy_token: "set", llm_api_key: "not set" },
  };
}
