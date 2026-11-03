// Test data in the API shapes.
import type { components } from "@/api/schema";

type ContainerOut = components["schemas"]["ContainerOut"];
type ContainerDetail = components["schemas"]["ContainerDetail"];

/** A running, healthy container with no update. */
export function container(fields: Partial<ContainerOut> = {}): ContainerOut {
  return {
    name: "web",
    state: "running",
    health: "healthy",
    image: "nginx",
    tag: "1.27.0",
    status: "up to date",
    latest_version: "1.27.0",
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
