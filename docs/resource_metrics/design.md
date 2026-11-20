# Design: resource metrics and the Overview page

## Goal

WT shows the resource use of the Docker VM (the OrbStack Linux VM) and of each app and container: current values and graphs with a timeline dropdown.

### Scope
 - New home page **Overview** (`/`): VM values and graphs, app and container counts, the app list with CPU and memory.
 - **App details** (`/apps`): the current container list, plus CPU and memory in each row and a **Logs** button.
 - Container page: a **Resources** section.
 - Setting: poll interval.

### Not in scope
 - macOS host metrics.
 - Alerts on resource use.
 - An app page (an app click opens App details at its group).
 - Peak (max) values. The tiers keep averages only.

## Decisions

| # | Topic | Choice |
|---|---|---|
| D1 | Container metrics | Docker stats API, `stream=false&one-shot=true`, one call per running container per poll. The admin sets the interval. |
| D2 | VM metrics | WT reads `/proc` in its own container and `statvfs` on the data dir. All four metric groups. |
| D3 | Storage | SQLite tiers. Ranges 1h, 6h, 24h, 7d, 30d. Interval 5, 10, 15, 30 or 60 s (default 10 s). |
| D4 | Live data | SSE `metrics` event. The UI fetches the open queries again. |
| D5 | Charts | uPlot for large charts. Own SVG sparkline in rows. |
| D6 | Numbers | CPU % of the VM, plus cores. Memory `usage - inactive_file`. App = Compose project, a container with no project is its own app. WT polls only running, shown containers. |
| D7 | Pages and API | `/` Overview, `/apps` App details. New `/api/metrics` router. An app click opens `/apps` at its group. |

## Design

### Data flow

```
metrics worker (each interval)
  |- Docker stats (one-shot) for each running, shown container --> counters
  |- /proc/stat, meminfo, loadavg, uptime, diskstats; statvfs(/data)
  |- calc: deltas -> CPU %, cores, rates (in memory: last counters, current values)
  |- each minute: average of the samples -> 1m rows (SQLite) -> SSE metrics {kind: history}
  '- each poll: SSE metrics {kind: current}
rollup (in the worker): 1m -> 15m each 15 min, 15m -> 1h each hour
cleanup worker (hourly): delete rows older than the tier retention
```

The worker makes its own Docker client (`ctx.docker_factory`). It polls with at most 10 calls at the same time.

### Numbers (the backend calculates all values)

| Value | Rule |
|---|---|
| Container CPU % | `Δcpu_usage.total / Δsystem_cpu_usage × 100` (% of all VM cores). Cores = same ratio × `online_cpus`. |
| Container memory | `usage - inactive_file`. Limit: the container limit, or the VM total when there is no limit. |
| Rates (net, disk I/O) | Δbytes / Δtime of the Docker `read` time. A counter that goes down (restart) gives no value. |
| First poll of a container | No CPU or rate value ("-"). |
| VM CPU % | `/proc/stat` line `cpu`: 1 - Δ(idle + iowait) / Δtotal. Cores: the number of `cpuN` lines. |
| VM memory | `MemTotal - MemAvailable` of `MemTotal`. On OrbStack, `MemTotal` is the memory limit of OrbStack. |
| VM swap, load, uptime | `/proc/meminfo`, `/proc/loadavg`, `/proc/uptime`. |
| VM disk | `statvfs` of the data dir (the Docker disk). Disk I/O: `/proc/diskstats` of the devices in `/sys/block`, not `loop*`, `ram*`, `zram*` or `dm-*`. |
| VM network | Sum of the container rates. WT has its own network namespace, so it cannot see the VM network. |
| App values | Sum of its containers. |
| Counts | Apps: Compose projects + containers with no project. Containers: running of all shown. `wt.enable=false` containers are not counted or polled. |

### Storage

Two tables, so that each column has one meaning and no nulls:
 - `vm_sample`: host_id, tier, time, cpu_percent, mem_used, mem_total, swap_used, swap_total, load_1, load_5, load_15, disk_used, disk_total, disk_read_bps, disk_write_bps, net_rx_bps, net_tx_bps. PK (host_id, tier, time).
 - `container_sample`: container_id (FK, cascade), tier, time, cpu_percent, mem_used, mem_limit, net_rx_bps, net_tx_bps, disk_read_bps, disk_write_bps. PK (container_id, tier, time).

The key is `container.id`, so the history stays after a recreate (the name stays).

| Tier | Built from | Kept for | Used by ranges |
|---|---|---|---|
| 1m | average of the polls in the minute | 24 h | 1h, 6h, 24h, sparklines |
| 15m | average of 1m rows | 7 d | 7d |
| 1h | average of 15m rows | 30 d | 30d |

Size: about 2,900 rows per container (about 30 MB for 100 containers).

### API (all under `/api/metrics`, session needed)

| Route | Gives | The UI fetches again on |
|---|---|---|
| `GET /overview` | VM current values with labels, counts, groups in the order of `/api/containers` with sums and container current values, the ranges list | `metrics` current |
| `GET /sparklines` | Last 60 min of 1m CPU and memory for each group and container. Null for a gap. | `metrics` history |
| `GET /vm/history?range=` | Times, and a series list (key, label, unit, values) | `metrics` history |
| `GET /containers/{name}/history?range=` | Same as the VM. 404 if the container is not in Docker now. | `metrics` history |

The backend gives the labels of the current values (for example `9% (1.0 core)`, `3.1 / 8.0 GiB`). The frontend formats only the chart axis ticks, from the `unit` of the series.

Refinement of D7: the sparklines have their own route. They change once a minute, so the overview (fetched at each poll) stays small.

### UI

 - Top nav: Overview, Apps, Settings. The sidebar does not change.
 - **Overview**: VM tiles (CPU, memory, swap, disk, disk I/O, network, load, uptime), VM charts (CPU, memory, disk I/O, network, load) each with the shared range dropdown, counts (link to `/apps`), the app list (group header with sums and sparkline, container rows with CPU, memory and sparkline). A container opens its page. A group opens `/apps?group=<label>`.
 - **App details**: the current page, plus CPU and Memory columns (label and sparkline) and a Logs button in each row. `?group=` opens that group and scrolls to it.
 - **Container page**: a Resources section with the current values and charts for CPU, memory, network and disk I/O.
 - **Settings**: poll interval select.
 - All charts use one shared range. Each chart has the range dropdown. A change in one dropdown changes all charts on all pages. The browser keeps the range in localStorage (`wt.metricsRange`, default 1h).
 - Charts have an `aria-label`. The current values are text next to each chart.
 - The ntfy digest message links to `/apps` (it linked to `/`, which is now the Overview).

### Settings

`metrics_interval_seconds`: 5, 10, 15, 30 or 60. Default 10. The worker reads it again on the `settings` bus message. It is in the config export.

### To verify on the OrbStack server

 - The Docker Engine is 25 or later (one-shot gives correct values).
 - `/proc/meminfo`, `/proc/stat` and `/sys/block` in the WT container show the VM.
 - Idle RAM stays below 200 MB with 50 more containers at a 10 s interval (footprint test).
