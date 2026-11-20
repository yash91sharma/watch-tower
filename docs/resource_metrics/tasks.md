# Tasks: resource metrics and the Overview page

Design: `design.md` (this folder). Do the sections in sequence, and the tasks in a section in sequence.

Rules:
 - TDD: write the failing test (**Test**) first. Then write the code.
 - A task is done when its tests and `.devcontainer/check.sh` pass in `wt_dev`. One commit per task: "<summary> (task M.N)".
 - Run all tools in `wt_dev`. Name test containers `wt_test_<suffix>`.
 - Thin frontend: the backend makes all decisions and labels.

## 1. Backend: collect and store

- [x] **1.1** Setting `metrics_interval_seconds` in `Settings` (`wt/config.py`): `Literal[5, 10, 15, 30, 60]`, default 10.
  - **Test:** default, a value not in the list fails validation, the config export and import have it.
- [x] **1.2** Docker stats in `wt/docker/client.py`: dataclass `ContainerStats` (read time, cpu_total, system_cpu, online_cpus, mem_usage, mem_inactive_file, mem_limit, net_rx, net_tx, disk_read, disk_write), parser `container_stats(data)`, `DockerApi.stats(container_id)` with `stream=false&one-shot=true`. Add `stats` to `FakeDocker` (the test sets the counters).
  - **Test:** the parser with a sample from Docker 29 (cgroup v2), with no `networks` and with no `blkio` values. Docker test (`-m docker`): `stats` of `wt_test_healthy` through the socket proxy gives counters in less than 200 ms.
- [x] **1.3** `wt/metrics/calc.py`: pure functions for container CPU % of the VM, cores, memory used, byte rates. A counter that goes down gives None.
  - **Test:** sample values. Hypothesis: CPU % is in 0..100 and cores are in 0..online_cpus for each valid pair of samples.
- [x] **1.4** `wt/metrics/vm.py`: read `/proc/stat`, `/proc/meminfo`, `/proc/loadavg`, `/proc/uptime`, `/proc/diskstats`, `/sys/block` and `statvfs(data_dir)`. The root dir is a parameter (tests give a fixture dir). VM CPU % and disk rates come from the delta of two reads (use `calc`).
  - **Test:** fixture files give the expected values. `loop*`, `ram*`, `zram*`, `dm-*` and `nbd*` are not counted. A missing file raises a clear error. Docker test: a read in `wt_dev` (a container on the VM) gives the `MemTotal` and `NCPU` of `docker info`.
- [x] **1.5** Tables `vm_sample` and `container_sample` and enum `MetricTier` (`1m`, `15m`, `1h`) in `wt/db/models.py`. Alembic revision `0002`.
  - **Test:** upgrade from `0001` and from the dumps. `alembic check` finds no drift. A delete of a container row deletes its samples. A second row with the same key fails.
- [x] **1.6** `wt/metrics/sampler.py`: one poll gets the stats of the running, shown containers (from `Inventory`, max 10 calls at the same time) and the VM values. It keeps the last counters and the current values in memory. After each poll it publishes `metrics {kind: current}`. At each new minute it writes the average of the polls of the last minute as `1m` rows in one transaction and publishes `metrics {kind: history}`.
  - **Test (fake clock, FakeDocker):** the first poll gives no CPU value, the second does. A minute writes one row per container and one VM row with the averages. A stopped or removed container is dropped from the current values. Docker down: the poll skips the containers, keeps the VM values and does not stop.
- [x] **1.7** Rollup and retention in `wt/metrics/store.py`: at each 15-min boundary, write `15m` rows from the `1m` rows of that 15 min. At each hour, write `1h` rows from the `15m` rows. `cleanup.delete_old_rows` deletes `1m` rows older than 24 h, `15m` older than 7 d, `1h` older than 30 d.
  - **Test:** averages are correct. A second rollup of the same period changes nothing. The cleanup keeps the rows in the retention and deletes the older ones.
- [x] **1.8** `metrics_worker` in `wt/main.py` `WORKERS`. It waits for `inventory.synced`, runs a poll at each interval, makes its own Docker client (`ctx.docker_factory`) and makes a new one after `DockerUnavailableError`. It reads the interval again on the `settings` bus message.
  - **Test:** a settings change changes the time between polls. A cancel stops the worker and closes the client.

## 2. Backend: API

- [x] **2.1** `wt/metrics/labels.py`: labels for bytes (`3.1 GiB`), used of total (`3.1 / 8.0 GiB`), rates (`1.2 MB/s`), CPU (`9% (1.0 core)`), load (`0.52 / 0.40 / 0.35`) and uptime (`3 d 4 h`). None gives `-`.
  - **Test:** sample values, units at each boundary.
- [x] **2.2** `GET /api/metrics/overview` in `wt/api/metrics.py`: VM current values with labels, counts (apps rule and running of all), the groups in the order of `/api/containers` with sums and container current values, the ranges list (key and label), the interval. A stopped container has null values and `-` labels.
  - **Test:** the apps count with projects and with containers that have no project. An excluded container is not counted. The group sums. Before the first poll, all values are null.
- [x] **2.3** `GET /api/metrics/sparklines`: the last 60 min of `1m` CPU and memory for each group (sum) and each container, on 60 fixed minute slots. Null for a gap.
  - **Test:** a gap gives null. A group value is the sum of its containers in that slot.
- [x] **2.4** `GET /api/metrics/vm/history?range=` and `GET /api/metrics/containers/{name}/history?range=`. Range to tier: 1h, 6h, 24h use `1m`; 7d uses `15m`; 30d uses `1h`. The response has the slot times and a chart list. Each chart has a key, a title, a unit, a y max (100 for a percent, the memory total or limit) and its series (key, label, values).
  - **Test:** each range reads its tier and time window. Bad range: 422. Unknown container: 404. The container history stays after a recreate (same name).
- [x] **2.5** SSE: add `Topic.METRICS` to the `/api/stream` topics. Run `pnpm gen:api`.
  - **Test:** a client gets `event: metrics` with `kind`. The OpenAPI and Schemathesis contract tests pass.

## 3. Frontend

- [x] **3.1** Queries for the 4 metric routes. `useEventStream`: `metrics` current fetches the overview again, `metrics` history fetches the sparklines and the open history queries again.
  - **Test:** each event kind fetches only its queries again (MSW).
- [x] **3.2** `components/Sparkline.tsx`: an SVG line from the values. A null makes a gap. It has no axes.
  - **Test:** the path for sample values, a gap, all null.
- [x] **3.3** Add the dependency `uplot`. `useMetricsRange()`: one shared range for all charts, kept in localStorage (`wt.metricsRange`, default `1h`). `components/MetricChart.tsx`: a uPlot wrapper with a title, a range select (the ranges from the API, value from `useMetricsRange`), a tooltip, the theme colors from CSS variables (light and dark) and resize. It formats the axis ticks from the series `unit`. It has an `aria-label`.
  - **Test (uPlot mocked in jsdom):** a range change in one chart changes the select and the fetched range of all charts. After a reload the range stays. The series labels are in the legend. The ticks for each unit.
- [x] **3.4** Routes: `ContainersPage` becomes `AppsPage` at `/apps`. `/` opens the new `OverviewPage` (empty frame for now). Top nav: Overview, Apps, Settings. Breadcrumbs say "Apps". The ntfy digest message (`wt/notify/messages.py`) links to `/apps`.
  - **Test:** the routes, the nav links, the breadcrumb on the container page and logs page, the digest click URL.
- [x] **3.5** App details: CPU and Memory columns (label and sparkline) and a Logs button in each row. The group header shows the sums. `?group=<label>` opens that group and scrolls to it.
  - **Test:** a row shows the labels from the API. Logs opens `/containers/<name>/logs`. `?group=` opens a collapsed group.
- [x] **3.6** Overview page: VM tiles, VM charts (CPU, memory, disk I/O, network, load), counts with a link to `/apps`, the app list (group header with sums and sparkline, container rows with CPU, memory and sparkline). A container opens its page. A group opens `/apps?group=<label>`.
  - **Test:** the tiles and counts from the API. The links. No containers: the text from `ContainersPage`.
- [ ] **3.7** Container page: Resources section with the current values and charts for CPU, memory, network and disk I/O.
  - **Test:** the current labels. A stopped container shows `-` and the charts of its history.
- [ ] **3.8** Settings page: a select for the poll interval.
  - **Test:** a save sends the value. The select has the 5 values.

## 4. E2E and checks by hand

- [ ] **4.1** E2E flows: the Overview shows the VM values and the counts. A range change on one chart changes all charts, also on the container page. App details shows CPU in the rows. The container page shows the Resources charts. A change of the interval saves. Update the a11y spec and the visual snapshots (Overview, App details, container).
- [ ] **4.2** Socket proxy test: `GET /containers/{id}/stats` is allowed (`tests/docker/test_proxy.py`).
- [ ] **4.3** Footprint test by hand: with 50 more containers and a 10 s interval, idle RAM stays below 200 MB.
- [ ] **4.4** On the OrbStack server: check the 3 items in "To verify" of `design.md`.

## 5. Docs and release

- [ ] **5.1** README: the Overview page, the meaning of the numbers (CPU % of the VM, memory, OrbStack memory limit, VM network = sum of containers), the interval setting, the DB size.
- [ ] **5.2** At the release: add the DB dump of the new version in `backend/tests/fixtures/db/` (the release adds migration `0002`).
