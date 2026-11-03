# Tasks: WT v0.0.0

Scope: P0 in `design_doc.md`. Do the sections in sequence, and the tasks in a section in sequence.

Rules:
 - TDD: write the failing test (**Test**) first. Then write the code.
 - A task is done when its tests and `.devcontainer/check.sh` pass in `wt_dev`.
 - Run all tools in `wt_dev`. Name test containers `wt_test_<suffix>`.
 - Thin frontend: the backend makes all decisions. The frontend shows what the API sends. Exception: log search and JSON pretty-print.

## 1. Dev environment and repo

- [x] **1.1** Dev container `wt_dev`: Python 3.14, uv, Node 24, pnpm, Docker CLI, host Docker socket.
- [x] **1.2** Pre-commit hook runs `check.sh` in `wt_dev`.
- [x] **1.3** Make `backend/wt/` a package (`package = true`). Add script `wt = "wt.cli:main"` with argparse subcommands `serve`, `reset-admin`, `openapi` (stubs).
  - **Test:** `wt --help` exits 0 and lists the 3 subcommands. Each stub exits with a "not implemented" error.
- [x] **1.4** Add runtime deps: `fastapi`, `uvicorn`, `sqlmodel`, `alembic`, `aiodocker`, `httpx`, `pydantic-settings`, `argon2-cffi`, `pyotp`, `segno`. Lock with `uv lock`.
  - **Test:** a smoke test imports each package.
- [x] **1.5** Add dev deps: `hypothesis`, `respx`, `testcontainers`, `schemathesis`, `mutmut`, `pip-audit`, `pytest-cov`. Configure:
  - ruff: default rules, `S` (security), `TID251` (banned APIs, see 2.1 and 6.2).
  - pyright: strict on `wt/` and `tests/`.
  - pytest: anyio plugin for async tests. Markers `docker`, `e2e`, `llm_eval`. The default run skips them. CI runs them.
  - mutmut: run pytest with `-n0` (mutmut does not work with xdist).
  - **Test:** a sample async test and a sample Hypothesis test pass.
- [x] **1.6** Frontend scaffold: Vite, React 19, TypeScript strict, ESLint (typescript-eslint, react-hooks), Tailwind CSS, shadcn/ui, React Router, TanStack Query, TanStack Virtual, openapi-fetch, openapi-typescript. Vite proxies `/api` to the backend.
  - **Test:** `pnpm build`, `pnpm lint` and `tsc --noEmit` pass.
- [x] **1.7** Frontend test tools: Vitest, `jsdom`, Testing Library, MSW, `@vitest/coverage-v8`. Shared MSW handlers in `src/test/`. Remove `smoke.test.ts`.
  - **Test:** a sample component test with an MSW handler passes.
- [x] **1.8** Extend `check.sh`: ruff, pyright, pytest with coverage gate (backend ≥ 90% line and branch), `tsc`, ESLint, Vitest with coverage ≥ 85% (exclude `src/main.tsx` and `src/api/schema.d.ts`). Tasks 7.1, 9.1 and 10.1 add the 100% branch gates for their modules.
  - **Test:** a lint error makes `check.sh` fail. A missed branch makes it fail.
- [x] **1.9** Dev run: publish `127.0.0.1:8000` (API) and `127.0.0.1:5173` (Vite) from `wt_dev`. Add `.env.dev.example` with no secrets.
  - **Test:** the host browser opens the app that runs in `wt_dev`.
- [ ] **1.10** PR workflow `.github/workflows/pr.yml`: build the dev image, run `check.sh` in it. Pin all actions by commit SHA.
  - **Test:** a PR runs the workflow and it passes.

## 2. Backend core

- [x] **2.1** `wt/clock.py`: `now()` (UTC, timezone-aware) and `async sleep(seconds)`. Pytest fixture `clock` sets the time. In tests, `sleep` moves the time with no real wait. Ban `datetime.now`, `datetime.utcnow`, `time.time` and `asyncio.sleep` outside `clock.py` (ruff `TID251`).
  - **Test:** the fixture sets and moves the time. A banned call in another module fails ruff.
- [x] **2.2** `wt/config.py` env vars (pydantic-settings): `DOCKER_HOST`, `WT_DATA_DIR` (default `/data`), `WT_TRUSTED_PROXIES`, `WT_LOG_LEVEL` (default `INFO`), `WT_GITHUB_API_URL` (default `https://api.github.com`). Secrets `WT_GITHUB_TOKEN`, `WT_NTFY_TOKEN`, `WT_LLM_API_KEY` are `SecretStr`. Each secret also reads `<NAME>_FILE`.
  - **Test:** defaults, `_FILE` read, error if `<NAME>` and `<NAME>_FILE` are both set, no secret value in `repr` or `str`.
- [x] **2.3** Logging: stdlib, stdout, level from `WT_LOG_LEVEL`, one line per record with time and module.
  - **Test:** a log of the config object shows no secret value.
- [x] **2.4** `wt/db/`: SQLite at `{WT_DATA_DIR}/wt.db`, `check_same_thread=False` (FastAPI runs sync code in threads). A SQLAlchemy `connect` listener sets WAL, `foreign_keys=ON` and `busy_timeout` on each connection. Sync SQLModel sessions. Make the data dir at start. DB file mode 600.
  - **Test:** pragmas on each new connection, file mode, use from a second thread.
- [x] **2.5** Tables. `container` has `host_id` (FK to `host`). `update` and `event` link to `container`.
  - `container`: id (PK), host_id, name, docker_id, compose_project, image, tag, enabled, release_source, source_confirmed. `docker_id`, `image` and `tag` can be null (an import adds rows before Docker sees them). Unique (host_id, name). Keep the row when the container is removed, so that admin values stay after a recreate.
  - `repo_cache`: repo (PK), etag, latest_tag, releases (JSON), fetched_at, error.
  - `update`: id (PK), container_id, from_version, to_version, severity, summary, release_notes, notified_at. Unique (container_id, to_version).
  - `event`: id (PK), container_id, kind (`became_unhealthy`, `recovered_health`, `restart_loop`, `recovered_loop`), time.
  - `setting` (key PK, value JSON), `admin` (id PK, password_hash, totp_secret, last_totp_step), `session` (token_hash PK, created, expires, last_seen).
  - **Test:** unique constraints reject duplicates.
- [x] **2.6** Alembic in `wt/db/migrations/`. The first revision makes all tables. WT runs `upgrade head` at start.
  - **Test:** upgrade from empty to head. `alembic check` finds no drift.
- [x] **2.7** At first start, add the host row: id 1, name `local`.
  - **Test:** two starts give one host row.
- [x] **2.8** Migration test with data: `tests/fixtures/db/` holds one SQL dump per release. The test loads each dump and upgrades to head. Task 18.6 adds the first dump.
  - **Test:** the test passes with 0 dumps and with 1 dump.

## 3. App base

- [x] **3.1** `wt/main.py`: `create_app()` (routes in `wt/api/`) and a lifespan that starts and stops the workers. `create_app()` adds Uvicorn `ProxyHeadersMiddleware` with trusted hosts from `WT_TRUSTED_PROXIES` (empty: an empty list, trust no proxy). `wt serve` runs Uvicorn: 1 worker, port 8000, root path only, `proxy_headers=False`.
  - **Test:** the lifespan starts and stops fake workers with no task leak. A test-only route gives `request.client.host` and `request.url.scheme`: WT uses `X-Forwarded-For` and `X-Forwarded-Proto` only from a trusted IP.
- [x] **3.2** Cleanup worker, each hour: delete expired sessions and `event` rows older than 7 days.
  - **Test (clock):** 8-day events and expired sessions go. 6-day events and valid sessions stay.
- [x] **3.3** `wt/bus.py`: in-process event bus, one asyncio queue per subscriber. Topics: `container`, `check`, `docker`, `settings`. Publish never blocks. A slow subscriber loses its oldest items.
  - **Test:** 2 subscribers get an event. Close removes a subscriber. A slow subscriber does not block.
- [x] **3.4** `GET /api/health` (no auth): 200 if the DB answers, else 503.
  - **Test:** both cases.
- [x] **3.5** Errors: one JSON shape `{error, detail}` for all errors, 422 included. No stack trace goes to the client.
  - **Test:** a route that raises gives 500 with no trace.
- [x] **3.6** Security headers on all responses: `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'` (Radix adds `<style>` elements), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`.
  - **Test:** headers on an API response and on `index.html`.
- [x] **3.7** Static files: serve the built frontend. Paths outside `/api` that are not files return `index.html`. Unknown `/api/*` paths return JSON 404. Hashed assets get a long cache. `index.html` and the service worker get `no-cache`.
  - **Test:** asset, SPA route, unknown API path, cache headers.

## 4. Auth

- [x] **4.1** `wt/auth/password.py`: Argon2id hash and verify (19 MiB, 2 iterations, 1 lane). Minimum password length 12.
  - **Test:** params in the hash string, good and bad password, short password.
- [x] **4.2** `wt/auth/totp.py`: new secret, provisioning URI (issuer `Watch Tower`), verify with 30 s step and ±1 step window. Check steps -1, 0 and +1 at `clock.now()` and return the matched step (pyotp `verify` gives only a bool). Reject a step ≤ `last_totp_step` (replay).
  - **Test:** codes at -1, 0 and +1 steps pass and give the step. ±2 fail. The same code twice fails.
- [x] **4.3** `wt/auth/limit.py` login limit: count failures in memory. After 5 failures, block for 15 minutes (time from `clock`). A success resets the count. Setup (4.6) and login (4.7) use it.
  - **Test (clock):** 5 failures block, 15 minutes later it unblocks, a success resets the count.
- [x] **4.4** Setup token: at start, if no admin is set up, make a random token (32 bytes) and log it once. Keep the token in memory only. Single use.
  - **Test:** WT logs the token once. The token stays the same until use. It fails after use. With an admin, WT makes no token.
- [x] **4.5** Sessions: random token (32 bytes) in cookie `wt_session` (`HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`). Store the SHA-256 hash. Expire after 30 days with no use. Each request updates `last_seen` and the expiry.
  - **Test:** cookie flags, expiry (clock), sliding expiry, no plain token in the DB.
- [x] **4.6** Setup API:
  - `GET /api/auth/state` gives `{setup_required, logged_in}`.
  - `POST /api/auth/setup/begin {token}` gives `{totp_secret, otpauth_uri, qr_svg}`. WT keeps the pending secret in memory.
  - `POST /api/auth/setup/finish {token, password, totp_code}` checks the code against the pending secret, saves the admin with the matched step as `last_totp_step`, clears the token and sets a session cookie (4.5).
  - Compare tokens in constant time. Wrong token: 403 and a failure for the limit (4.3). While the limit blocks: 429 with `Retry-After`. Admin exists: 409.
  - **Test:** full flow, wrong token, wrong code, second setup, 429 when blocked, the setup code fails at login (replay).
- [x] **4.7** `POST /api/auth/login {password, totp_code}`: one error message for all failures. Each failure counts for the limit (4.3). While the limit blocks: 429 with `Retry-After`.
  - **Test:** good login, wrong password, wrong code, 6th attempt gets 429, login works after 15 minutes.
- [x] **4.8** `POST /api/auth/logout`: delete the session row and the cookie.
  - **Test:** the old cookie gets 401.
- [x] **4.9** Auth guard: one dependency on a protected `/api` router. All routes except `/api/health` and `/api/auth/*` go on this router.
  - **Test:** a dummy route on the router gives 401 with no cookie. A test reads all registered `/api` routes. Each route not in the list gives 401 with no cookie. Later routes (SSE, `logs.txt`) get this test automatically.
- [x] **4.10** `wt reset-admin`: delete the password, TOTP secret and all sessions. Print "Restart WT (docker restart wt). Then get the setup token from the WT log."
  - **Test:** after a reset and a restart, `/api/auth/state` gives `setup_required`, old sessions get 401, WT logs a new token, the login limit is clear.

## 5. Settings and config

- [x] **5.1** UI settings in `wt/config.py`, stored as rows in `setting`: `check_interval_hours` (24, min 1), `restart_count` N (3, min 2), `restart_window_minutes` M (10, min 1), `ntfy_url`, `ntfy_topic`, `llm_url`, `llm_model`, `public_url`. URLs must be `http` or `https`.
  - **Test:** defaults on an empty DB, save and load, bad values fail.
- [x] **5.2** `GET /api/settings`: values and secret state (`github_token`, `ntfy_token`, `llm_api_key`: `set` or `not set`). `PUT /api/settings`: validate and save. A bad value gives 422 with one error per field. A save publishes `settings` on the bus.
  - **Test:** no secret value in a response. A save publishes `settings`.
- [x] **5.3** `GET /api/config/export`: JSON `{format_version, settings, containers: [{name, release_source, source_confirmed}]}`, file name `wt-config-<date>.json`. No secrets.
  - **Test:** with all secrets set, the export has no secret.
- [x] **5.4** `POST /api/config/import?dry_run=true|false` (JSON body): check `format_version` and all values, then save settings and per-container values by name in one transaction. Add rows for names that WT does not know yet. Return counts. A dry run returns counts and errors and saves nothing. A real import publishes `settings` on the bus.
  - **Test:** import of an export into an empty DB gives the same export. A bad file changes nothing. A dry run changes nothing. A real import publishes `settings`.

## 6. Docker access

- [x] **6.1** Docker test fixtures. Busybox images in `e2e/fakes/containers/`: healthy, unhealthy, restart loop, JSON logs (stdout and stderr), TTY, `latest` tag, excluded (`wt.enable=false`), versioned with `org.opencontainers.image.source`. All containers start healthy and stay running:
  - Unhealthy image: healthy while `/tmp/ok` exists (made at start). A test removes it with `docker exec`.
  - Restart loop image (`restart: on-failure`): a test writes K to `/tmp/crash` with `docker exec`. The container exits on the next K starts, then runs.
  - Each test sets its container back to healthy at the end.
  - Build all files into the images. No bind mounts (the Docker daemon is on the host, not in `wt_dev`).
  - The fixture makes network `wt_test_net`, connects `wt_dev` to it, and starts the socket proxy and the containers on it as `wt_test_*`. It reuses them if they exist.
  - **Test:** the fixture starts all containers healthy. A second run reuses them. `wt_dev` reaches the socket proxy by name.
- [x] **6.2** `wt/docker/client.py`: aiodocker client from `DOCKER_HOST`: `ping`, `list_containers` (all), `inspect`, `events`, `logs`. Typed return values. `FakeDocker` with the same interface for tests with no Docker. Ban `aiodocker` imports outside `wt/docker/` (ruff `TID251`).
  - **Test:** Docker test: ping and list through the socket proxy.
- [x] **6.3** Parse rules (pure):
  - Name: no leading `/`.
  - Compose project: label `com.docker.compose.project`.
  - Excluded: label `wt.enable` is `false` (any case).
  - Image reference: repo and tag. Handle a registry with a port and an `@sha256` digest. No tag means `latest`. Digest only means no tag.
  - Release source: label `org.opencontainers.image.source` (Docker copies image labels to the container). Accept `https://github.com/<owner>/<repo>` (remove `.git` and extra path) and `owner/repo`. Give `owner/repo`. Other values give no source.
  - **Test:** table tests, release source with a GitLab URL, bad URL, `.git`, extra path. Hypothesis: any string gives a result or a typed error, never a crash.
- [x] **6.4** Inventory: at start, list and inspect all containers. Keep live state (state, health, docker_id) in memory. Upsert `container` rows by (host_id, name). Set `release_source` from the label (6.3) only if `source_confirmed` is false. Excluded containers get `enabled=false` and no more work.
  - **Test:** Docker test: Compose groups, excluded container, a recreate keeps the confirmed source, a non-GitHub label gives no source.
- [x] **6.5** Events worker: read the `events` stream for containers (`start`, `die`, `health_status`, `destroy`). After each event except `destroy`, inspect the container again, update the inventory and publish `container` on the bus. On `destroy`, remove the container from the inventory only if its `docker_id` matches the current one for that name.
  - **Test:** Docker test: start and stop a test container, get the events. A `destroy` with an old `docker_id` keeps the new container.
- [x] **6.6** Connection: at start and when the stream stops, publish `docker` disconnected, wait with backoff (1 s, doubles, max 60 s, through `clock`), connect, list all again, publish `docker` connected. Keep the current connection state in memory (11.3 reads it).
  - **Test:** a fake stream that fails twice. Docker test: restart the socket proxy, the inventory syncs.
- [x] **6.7** Log reader: `logs(name, tail, since, follow)` gives `LogLine(time, stream, text)`. Request timestamps. Split stdout and stderr from the multiplexed stream. A TTY container has one raw stream: all lines are `stdout`. If aiodocker drops the stream type, parse the 8-byte frame header.
  - **Test:** Docker test: tail, since, follow, stderr lines, TTY container.

## 7. Health

- [x] **7.1** `wt/health/rules.py` restart window (pure): count `start` events that follow a `die`. N or more in M minutes is a restart loop. The loop ends when no `start` comes in M minutes. Add a 100% branch gate for `wt/health/` to `check.sh`.
  - **Test:** N-1 starts: no loop. N starts: loop. N starts over more than M: no loop. M quiet minutes: loop ends.
- [x] **7.2** Health state machine (pure): flags `unhealthy` and `restart_loop` per container. Input: event (with `docker_id`) and time. Output: changes `became_unhealthy`, `recovered_health`, `restart_loop`, `recovered_loop`. One change per state change. `destroy` removes the state with no change, only if `docker_id` matches.
  - **Test:** each change. Repeated `unhealthy` events give one change. A `destroy` with an old `docker_id` keeps the state. 100% branch.
- [x] **7.3** Baseline: at start and after a resync (6.6), set the state from `inspect` with no change.
  - **Test:** a container that is unhealthy at start gives no change, then `recovered_health` when it becomes healthy.
- [x] **7.4** Health wiring: the events worker (6.5) calls the health rules directly (not through the bus, because the bus can drop items). After each connect (6.6), set the baseline (7.3). Save each change as an `event` row. A 30 s tick finds loop ends. N and M come from settings and reload on `settings`.
  - **Test (clock):** a restart loop, then M quiet minutes, gives `restart_loop`, then `recovered_loop`, and 2 `event` rows.
- [x] **7.5** Docker test: `docker exec` makes the unhealthy and restart loop containers fail (6.1). WT gives the expected changes.

## 8. Update summary (LLM)

- [x] **8.1** `wt/llm/severity.py`: `critical` if the notes contain `CVE-` or `security` (any case). Else `normal`.
  - **Test:** table tests.
- [x] **8.2** `wt/llm/client.py`: `POST {llm_url}/v1/chat/completions` with `model`, `messages`, `temperature: 0` and a strict `json_schema` `response_format` for `{severity: "critical" | "normal", summary: string}`. `Authorization: Bearer` if `WT_LLM_API_KEY` is set. Timeout 60 s. Validate the reply with Pydantic. On any error, log a warning and give no result.
  - **Test (respx):** good reply, timeout, HTTP 500, bad JSON, JSON that does not match the schema.
- [x] **8.3** Prompt: write the summary in ASD-STE100, max 2 sentences. Set `critical` for CVE or security fixes. Send the release notes in a separate message, as data. Cut the notes at 16,000 characters.
  - **Test:** prompt snapshot. Long notes are cut.
- [x] **8.4** `summarize(notes)`: if `llm_url` and `llm_model` are set and the LLM gives a result, use it. Else the summary is empty and the severity comes from 8.1.
  - **Test:** LLM off (URL or model not set), LLM error, LLM good.
- [x] **8.5** LLM eval: 20 release notes with the expected severity in `tests/llm_eval/`. A test with marker `llm_eval` calls a real Ollama and checks the severity and the reply schema.
  - **Test:** runs nightly (17.2).

## 9. Version check

- [x] **9.1** `wt/versions/rules.py` tag filter: a version tag is `v?`, then digits with dots, then an optional `-suffix`. Other tags (`latest`, `stable`, `main`, no tag) get `no check`. Add a 100% branch gate for `wt/versions/` to `check.sh`.
  - **Test:** table tests.
- [x] **9.2** Update rule: remove a leading `v` and any `-suffix` from both. Split into number parts. Short form: if the running version has fewer parts and they match the first parts of the latest, no update (`16` and `16.4` match `16.4.1`). Else pad with 0 and compare as numbers. Update only if the latest is higher (`1.2.0` = `1.2`).
  - **Test:** table tests: design cases, `1.2.0` vs `1.2`, running newer than latest. Hypothesis: no crash, same input gives same result, equal versions give no update.
- [x] **9.3** Release range: drop drafts, pre-releases and tags that are not versions. Keep versions above the running version, up to the latest (number compare). Sort newest first. Join the notes with one heading per version.
  - **Test:** table tests. Hypothesis: the generator makes a release list that has a valid latest version (not a draft, not a pre-release) above the running version. The result is a sorted subset that contains the latest.
- [x] **9.4** `wt/versions/github.py`: httpx client, base URL `WT_GITHUB_API_URL`, headers `Accept: application/vnd.github+json`, `X-GitHub-Api-Version`, `User-Agent`, `Authorization: Bearer` if the token is set. Timeout 30 s. `latest(repo, etag)` gives a release, `not modified` (304) or `no release` (404). `releases(repo)` gets one page, `per_page=100`.
  - **Test (respx):** 200, 304 with ETag, 404, timeout, bad JSON.
- [x] **9.5** Rate limit: 403 or 429 with `x-ratelimit-remaining: 0`, or a `Retry-After` header, raises `RateLimited(reset_at)`. The check run waits until the reset time (through `clock`), then continues.
  - **Test (respx, clock):** the run waits, then finishes.
- [x] **9.6** Repo cache: save ETag, latest tag, release list and fetch time in `repo_cache`. Get the release list only when the latest tag changes. A failed fetch, or a latest tag that is not a version (9.1), saves the error text. A good fetch clears it.
  - **Test:** a second run with 304 makes no release list call. A 404 saves an error. A latest tag `nightly` saves an error.
- [x] **9.7** Status (computed on read from tag, source and `repo_cache`, so it stays after a restart): `no check`, `no source`, `not checked`, `up to date`, `update`, `error`.
  - **Test:** each status.
- [x] **9.8** Check run `wt/versions/check.py`: take enabled containers with a version tag and a source. One call per repo. One run at a time (lock). Save the last run time and the status counts in `setting`.
  - **Test (respx):** 2 containers on one repo make 1 call. A second run during a run does not start.
- [x] **9.9** Update rows: for an update, upsert `update` by (container, to_version). New row: add release notes, severity and summary (8.4). Existing row: keep `notified_at`. If `from_version` changed, set it and make the release notes, severity and summary again (8.4). The current update of a container is the row with `to_version` = latest tag, when the status is `update`. One function gives it. 10.4, 11.1 and 11.2 use it.
  - **Test:** a second run makes no new row and no LLM call. A new running version makes new notes, one LLM call and no new message. Old rows are not current.
- [x] **9.10** Scheduler: an asyncio loop runs a check when `last run + interval` is past (no last run: now). It also runs on "Check now". It wakes on `settings`.
  - **Test (clock):** runs at the interval. A new interval takes effect. No run at start when not due.
- [x] **9.11** `POST /api/checks`: start a run (202), or 409 if a run is active. `GET /api/checks/status`: `{running, last_run, counts}`. Publish `check` at start and end.
  - **Test:** start, 409 during a run, status after the run.
- [x] **9.12** `PUT /api/containers/{name}/release-source {source, confirmed}`: validate with the 6.3 parse. `source: null` clears it and sets `source_confirmed=true`, so that the label does not come back.
  - **Test:** set, confirm, clear (a new inspect keeps it clear), bad value 422, unknown name 404.

## 10. Notifications (ntfy)

- [x] **10.1** `wt/notify/messages.py` (pure): title, body, tags and click link. ASCII in header values. Short body. Add a 100% branch gate for `wt/notify/` to `check.sh`.
  - One update: title `Update: <name> <from> -> <to>`. Body: the summary, or `Release notes are available`.
  - Digest: title `<n> updates`. One body line per container.
  - Health: `<name> is unhealthy`, `<name> restarts in a loop`, `<name> is healthy again`, `<name> does not restart now`.
  - Click: `<public_url>/containers/<name>`, or `<public_url>/` for a digest. No `Click` header if `public_url` is not set.
  - **Test:** text snapshots for each message.
- [x] **10.2** Priority: `high` for a critical update, a digest with a critical update, and `unhealthy`. Else `default`.
  - **Test:** table tests.
- [x] **10.3** `wt/notify/ntfy.py`: `POST {ntfy_url}/{topic}` with `Title`, `Priority`, `Tags`, `Click`, and `Authorization: Bearer` if `WT_NTFY_TOKEN` is set. Timeout 10 s. Give ok or fail. If the URL or topic is not set, send nothing.
  - **Test (respx):** headers, token, error, not set.
- [x] **10.4** After each check run: get the current update rows (9.9) with no `notified_at`. One row: one message. More rows: one digest. On success, set `notified_at`. On fail, keep the rows for the next run.
  - **Test:** 1 update, 2 updates, second run sends nothing, a failed send goes out on the next run, a stale row is not sent.
- [x] **10.5** Health: send one message for each change from 7.2, at once. On fail, log it.
  - **Test:** each change sends one message with the correct priority.

## 11. Containers API

- [x] **11.1** `GET /api/containers`: containers that exist in Docker now (any state) and are not excluded, in groups `[{project, label, containers}]`. Sort groups by label and containers by name. Containers with no Compose project go in the last group, label `Other`. Fields: name, state, health (`healthy`, `unhealthy`, `starting`, `none`), image, tag, status (9.7), latest version, severity of the current update (9.9), release_source, source_confirmed.
  - **Test:** groups, sort order, `Other`, fields per status, excluded container absent.
- [x] **11.2** `GET /api/containers/{name}`: fields from 11.1, the current update (9.9: from, to, severity, summary, release notes) and the events of the last 7 days. 404 for an unknown or excluded name.
  - **Test:** with and without an update.
- [x] **11.3** `GET /api/stream` (SSE): on connect, first send the current `docker` state (6.6). Then send bus events (`container`, `check`, `docker`). Keep-alive comment every 15 s. Headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Unsubscribe when the client goes.
  - **Test:** a new client first gets the `docker` state. A container change arrives. Keep-alive (clock). Disconnect removes the subscriber.
- [x] **11.4** OpenAPI: typed response models on all routes. `wt openapi` writes the schema. `pnpm gen:api` writes `frontend/src/api/schema.d.ts` (committed). `check.sh` makes both again and fails on a diff.
  - **Test:** a changed route model with old types makes `check.sh` fail.
- [x] **11.5** Contract: schemathesis on all routes, with a session and `FakeDocker`. No 500 errors. Short run on PRs.
  - **Test:** the schemathesis test passes.

## 12. Logs API

- [x] **12.1** `GET /api/containers/{name}/logs` (SSE): `tail` (default 500, max 10,000), `follow` (default true), `since`. One event per line: `{time, stream, text}`. Stop the Docker stream when the client goes. 404 for an unknown or excluded name.
  - **Test:** Docker test: tail, follow gets new lines, since, disconnect stops the Docker stream.
- [x] **12.2** `GET /api/containers/{name}/logs.txt`: the full log, no follow, `text/plain`, `Content-Disposition: attachment; filename=<name>-<date>.log`. Line format: `<time> <stream> <text>`. 404 for an unknown or excluded name.
  - **Test:** Docker test: content and headers. 404 for an excluded name.

## 13. Frontend

- [x] **13.1** App shell: nav (Containers, Settings, Log out), routes (`/setup`, `/login`, `/`, `/containers/:name`, `/containers/:name/logs`, `/settings`), not-found page, error boundary. Light and dark mode follow the system. Phone-width layout. Times in the browser time zone.
  - **Test:** each route renders. Not-found page.
- [x] **13.2** API client: openapi-fetch with the generated types, same-origin cookies. A 401 opens `/login`. TanStack Query provider.
  - **Test (MSW):** a 401 opens `/login`.
- [x] **13.3** Auth guard from `/api/auth/state`: setup required opens `/setup`. Logged out opens `/login`. Logged in opens the app.
  - **Test:** each state.
- [x] **13.4** Setup page. Step 1: token. Step 2: TOTP QR code (`qr_svg` in an `<img>` with a `data:` URL, not inner HTML), secret as text, password (two times), TOTP code. The page only checks that the two passwords match. It shows the backend errors. Success opens the app.
  - **Test:** full flow, wrong token, passwords that do not match, wrong code.
- [x] **13.5** Login page: password and TOTP code. After the login limit, show the wait time from `Retry-After`. The Log out button calls logout and opens `/login`.
  - **Test:** good login, error, 429 message, logout.
- [x] **13.6** `useEventStream` on `/api/stream`: update the TanStack Query cache. After a reconnect, refetch all queries. Show a banner when WT or Docker is disconnected.
  - **Test:** a container event updates the list. A reconnect refetches. The banner shows and hides.
- [x] **13.7** Containers page: groups in API order (11.1). Row: name, state, health badge (`none` shows `no healthcheck`), running tag, latest version, status, severity badge. Loading, empty and error states.
  - **Test:** groups in API order, each status, empty and error states.
- [x] **13.8** "Check now" button and last check time. The button is off during a run.
  - **Test:** a click starts a run. The button is off during the run.
- [ ] **13.9** Container page: state, health, events of the last 7 days, link to logs.
  - **Test:** renders MSW data.
- [ ] **13.10** Release source form: show the value, edit it, confirm it. Show "not confirmed" until the admin confirms.
  - **Test:** edit, confirm, clear, backend error.
- [ ] **13.11** Update block: running version, latest version, severity, summary, release notes. Plain text only.
  - **Test:** with and without a summary. A note or summary with `<script>` shows as text.
- [ ] **13.12** Logs buffer: read the `/logs` SSE. Keep max 10,000 lines (drop the oldest). Add new lines once per animation frame. Clear the buffer when the stream opens (a reconnect sends the tail again).
  - **Test:** buffer cap, batching, line parse, a reconnect gives no duplicate lines.
- [ ] **13.13** Logs view: TanStack Virtual list. Follow mode scrolls to the end. Scroll up pauses follow. A button starts follow again. Stderr lines have a different color. Tail size select.
  - **Test:** follow and pause.
- [ ] **13.14** Log search (in the browser): highlight, match count, next and previous, show only matches. Not case-sensitive.
  - **Test:** matches, no match, filter mode, case.
- [ ] **13.15** JSON pretty-print toggle (in the browser): JSON object lines show formatted. Other lines do not change.
  - **Test:** JSON line, bad JSON, plain text.
- [ ] **13.16** Log download button: link to `logs.txt`.
  - **Test:** the link URL.
- [ ] **13.17** Settings page: form for 5.1. Show the backend field errors. Show each secret as "set" or "not set" (read only; env vars set them).
  - **Test:** save, field errors, secret state.
- [ ] **13.18** Export and import. Export downloads the JSON. Import sends the file text to the dry run (5.4), shows the counts and errors, asks to confirm, then sends it to save.
  - **Test:** export, dry run then confirm, bad file error.
- [ ] **13.19** Accessibility: a label on each input, visible focus, keyboard use, color contrast in both modes.
  - **Test:** component tests find elements by role and label.

## 14. PWA

- [ ] **14.1** App icon (SVG source; PNG 192, 512 and maskable). vite-plugin-pwa manifest: name, short name, icons, theme color, `display: standalone`, `start_url: /`. `apple-touch-icon` and iOS meta tags.
  - **Test:** the build has a valid manifest and the icons.
- [ ] **14.2** Service worker: cache the app shell only. Navigation fallback to `index.html`. Never cache `/api/*`.
  - **Test:** the build config has the `/api` deny rule.

## 15. Packaging and deploy

- [ ] **15.1** `Dockerfile` (multi-stage): Node 24 and pnpm build the frontend. `python:3.14-slim` runs the backend (`uv sync`, no dev deps, bytecode compiled at build). Non-root user owns `/data`. Venv `bin` on `PATH`. Port 8000. `HEALTHCHECK` calls `/api/health` with Python. `ENTRYPOINT ["wt"]`, `CMD ["serve"]`. OCI labels: source, version, revision. Pinned base images.
  - **Test:** the image builds. 16.21 tests it.
- [ ] **15.2** `.dockerignore`: `.git`, `.env*`, `node_modules`, `.venv`, tests.
  - **Test:** the build context has no secrets.
- [ ] **15.3** `compose.yaml`: the design example, plus `restart: unless-stopped` and commented Traefik labels.
  - **Test:** `docker compose config` passes.
- [ ] **15.4** `.env.example`: all env vars from 2.2, empty secrets, one comment per line.
  - **Test:** the file and the `config.py` fields match.
- [ ] **15.5** `README.md`: purpose, deploy, first setup (`docker logs wt` gives the token), Traefik example, `wt reset-admin` then `docker restart wt`, backup (stop WT, copy the `wt-data` volume, start WT), env vars.

## 16. Full-stack tests

- [ ] **16.1** Fake GitHub API (`e2e/fakes/github/`, FastAPI): `/repos/{o}/{r}/releases/latest` with ETag, `/repos/{o}/{r}/releases`, rate limit mode, control route to set releases. It starts with no updates (latest = running version). Each flow adds its releases.
  - **Test:** unit tests.
- [ ] **16.2** Fake LLM API (`e2e/fakes/llm/`): `/v1/chat/completions` with modes good, slow (timeout), error.
  - **Test:** unit tests.
- [ ] **16.3** E2E test containers: the 6.1 images, plus two old-version containers on fake repos (one with `CVE-` in the notes).
- [ ] **16.4** `e2e/compose.test.yaml`: WT (built image, same settings as `compose.yaml`), socket proxy, ntfy server, fake GitHub, fake LLM, Traefik with a self-signed certificate, test containers. All names `wt_test_*`. WT and the support services have `wt.enable=false`. Add `--label=wt.enable=false` to `wt_dev` (`devcontainer.json`). Tests check only the E2E Compose project group.
  - **Test:** the stack starts and WT is healthy.
- [ ] **16.5** Playwright runner `e2e/playwright.Dockerfile`: the official Playwright image (tag matches `@playwright/test`) plus the Docker CLI from `docker:cli`. Container `wt_test_playwright` with `wt.enable=false` and the Docker socket. `ignoreHTTPSErrors`. Projects:
  - `flows`: Flows 1-12 (16.6-16.17) on Chromium at desktop size, in sequence.
  - Chromium and WebKit at desktop, iPhone and Pixel sizes: a read-only smoke spec (login, list, container, logs), accessibility and visual. They run after `flows` (project dependency).
  - Helpers: setup token from the WT log, TOTP codes, ntfy messages (JSON poll API), fake GitHub releases, M = 1 minute through settings, age a session row (`docker exec` with Python `sqlite3`), restart WT.
  - **Test:** a sample spec runs on all projects.
- [ ] **16.6** Flow 1, setup: token from the log, password, TOTP.
- [ ] **16.7** Flow 2, login: login, logout, wrong password, wrong TOTP, login limit (then restart WT to clear it), session expiry.
- [ ] **16.8** Flow 3, container list: Compose groups, excluded container absent, `latest` shows `no check`.
- [ ] **16.9** Flow 4, release source: value from the label, admin edits and confirms it.
- [ ] **16.10** Flow 5, Check now: add one release on fake GitHub. Versions, notes and summary show. ntfy gets one message with the WT link. A second run sends nothing.
- [ ] **16.11** Flow 6, two updates: add releases for 2 containers (one with `CVE-` in the notes). ntfy gets one digest with high priority.
- [ ] **16.12** Flow 7, LLM off and LLM timeout: add a new release for each case. Notes only, keyword severity.
- [ ] **16.13** Flow 8, health: `docker exec` makes the containers fail (6.1). Unhealthy, restart loop and each recovery send one ntfy message.
- [ ] **16.14** Flow 9, logs: live tail, search, JSON pretty-print, download.
- [ ] **16.15** Flow 10, settings: change values, export, delete the DB, restart WT, set up, import, export again: the same file.
- [ ] **16.16** Flow 11, CLI reset: `docker exec wt wt reset-admin`, `docker restart wt`, then the setup page.
- [ ] **16.17** Flow 12, Docker stream stops: restart the socket proxy. The banner shows, then the UI recovers. No false ntfy message.
- [ ] **16.18** Accessibility: `@axe-core/playwright` on each page. No serious or critical issues.
- [ ] **16.19** Visual: screenshots of the main pages at desktop and phone width, light and dark mode. The containers page screenshot covers only the E2E project group. Baselines from the Playwright image.
- [ ] **16.20** PWA (Playwright): valid manifest, service worker registers, app shell loads offline, `/api` not cached.
- [ ] **16.21** Image: Trivy finds no high or critical CVE. The user is not root. The healthcheck passes. Only `/data` and `/tmp` are writable. `linux/arm64` and `linux/amd64` start.
- [ ] **16.22** Footprint (nightly): with 50 test containers, WT idle RAM < 200 MB (`docker stats`). After 5 s of a log stream at 1,000 lines/s, a click on pause updates the UI in < 200 ms.
- [ ] **16.23** Mutation (nightly): mutmut on `versions/`, `health/`, `notify/` (pytest with `-n0`, 1.5). Score ≥ 80%.

## 17. CI

- [ ] **17.1** PR workflow jobs: static, unit, property, integration, Docker, migration, contract, auth, frontend unit, E2E, accessibility, visual, PWA, image, dependencies (`pip-audit`, `pnpm audit`). Cache the dev image and deps.
  - **Test:** all jobs pass on a PR.
- [ ] **17.2** Nightly workflow: mutation, LLM eval (Ollama service, small model), footprint, long schemathesis run.
  - **Test:** a manual trigger passes.
- [ ] **17.3** Release workflow: a `v*` tag builds `linux/arm64` and `linux/amd64` (buildx), pushes `ghcr.io/yash91sharma/watch-tower:<version>` and `:latest`, and makes a GitHub release with notes.
  - **Test:** a dry run builds both architectures.
- [ ] **17.4** Dependabot: `uv`, `npm`, `github-actions`, `docker` (`Dockerfile`, `.devcontainer/Dockerfile`).
- [ ] **17.5** Branch protection on `main` (the user sets it in GitHub): PRs only, all 17.1 jobs required.

## 18. Release v0.0.0

- [ ] **18.1** Each P0 requirement and each CUJ has an E2E flow. Coverage gates pass.
- [ ] **18.2** Security review: no secrets in code, logs, tests or Git history. Check cookie flags, auth guard, trusted proxies, security headers, socket proxy GET only.
- [ ] **18.3** Deploy to prod (OrbStack, M2) behind Traefik and Tailscale. Idle RAM < 200 MB.
- [ ] **18.4** Manual test of all CUJs on desktop, iPhone (PWA) and Android (PWA). Record the result in the PR.
- [ ] **18.5** Version `0.0.0` in `pyproject.toml` and `package.json`. Tag `v0.0.0`. Check the GHCR image and the release notes.
- [ ] **18.6** Add the v0.0.0 DB dump to `tests/fixtures/db/`.

## CUJ coverage

| CUJ | Tasks | E2E |
|---|---|---|
| Deploy WT with compose and env vars | 15.1-15.5, 17.3, 18.3 | 16.21 |
| First setup: token, password, TOTP | 4.1-4.6, 13.4 | Flow 1 |
| Log in, log out, login limit, session expiry | 4.3, 4.5, 4.7-4.9, 13.3, 13.5 | Flow 2 |
| See containers by Compose project, with state and health | 6.3-6.5, 11.1, 11.2, 13.7, 13.9 | Flow 3 |
| Exclude a container (`wt.enable=false`) | 6.3, 6.4, 11.1 | Flow 3 |
| Set and confirm the release source | 6.3, 9.12, 13.10 | Flow 4 |
| See updates: versions, notes, summary (schedule and "Check now") | 8.1-8.4, 9.1-9.11, 13.8, 13.11 | Flows 5, 7 |
| Get update messages: one or digest, once per version, critical is high | 10.1-10.4 | Flows 5, 6 |
| Get health messages: unhealthy, restart loop, recovery | 7.1-7.5, 10.5 | Flow 8 |
| Read logs: live tail, search, JSON, download | 6.7, 12.1, 12.2, 13.12-13.16 | Flow 9 |
| Change settings, export and import config | 5.1-5.4, 13.17, 13.18 | Flow 10 |
| Reset the admin from the host | 4.4, 4.10 | Flow 11 |
| WT recovers when the Docker stream stops | 6.6, 7.3, 7.4, 11.3, 13.6 | Flow 12 |
| Use WT as a PWA on phone and tablet | 13.1, 14.1, 14.2 | 16.19, 16.20 |
| Use WT behind a reverse proxy | 3.1, 15.3 | All (Traefik in 16.4) |
