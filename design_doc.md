## Objective

Watch Tower (WT) watches a home lab server: setup, traffic, devices and apps. WT finds issues, anomalies and risks, and flags them. Later, WT will also fix them.

WT runs on the home server. It connects to apps on the same Docker host, machine and network.

### Non-goals
 - WT does not watch how an app processes data.
 - WT does not make apps more efficient.

## Requirements

### P0: monitoring only

P0 is read-only. WT does not act on containers.

#### Containers
 - WT watches all containers on the host. Label `wt.enable=false` excludes a container.
 - WT groups containers by Compose project. Checks and notifications are per container.
 - Docker access goes through a read-only socket proxy.

#### Version check
 - Running version: the image tag.
 - Latest version: the latest GitHub release of the release source. GitHub excludes drafts and pre-releases from "latest".
 - Release source: from the image label `org.opencontainers.image.source`. The admin confirms, edits or clears it in the UI. The admin value stays after a recreate.
 - Update rule: remove a leading `v` and any `-suffix` from both versions. Compare the parts as numbers (a missing part is 0). Update only if the latest is higher, unless the running tag is a short form of the latest (`16` matches `16.4.1`).
 - Tags that are not versions (`latest`, `stable`, `main`, digest only) get no check. The UI shows "no check".
 - Runs every X hours (configurable) and on "Check now".
 - Optional GitHub token for API rate limits.

#### Update summary
 - Shows the running version, the latest version and the release notes between them.
 - Optional LLM summary, 1-2 lines: critical (CVE, security fix) or normal (features, fixes).
 - Without an LLM, WT shows the release notes only.
 - The UI shows release notes and summaries as plain text.

#### Health
 - Shows the container state and healthcheck status.
 - Notifies when a container becomes unhealthy, restarts N times in M minutes, or recovers.

#### Logs (like [Dozzle](https://github.com/amir20/dozzle))
 - Live tail, search, JSON pretty-print, download.
 - Streams from the Docker API. No log storage.

#### Notifications (ntfy)
 - Public or private ntfy server, optional token.
 - One update: one message. More than one: one digest.
 - WT notifies each version once. Critical updates use high priority.
 - Messages are short and link to WT.

### Platform
 - One container: frontend, backend, SQLite.
 - Deploy with docker-compose and env vars. Per-container rules use Docker labels. All other settings are in the UI. Config export and import.
 - Prod: OrbStack on macOS (M2). Dev: Docker on macOS.
 - Clients: web app and PWA (Android, iOS, iPadOS). A native Android app can come later.
 - Access: Tailscale -> Traefik -> WT. Cloudflare gives DNS and TLS. TLS ends at Traefik. WT must work behind any reverse proxy.
 - Idle RAM < 200 MB. The compose file sets CPU and memory limits.

### Auth
 - One admin user. Password and TOTP.
 - No other users, no SSO, no self-service recovery. Host access can reset the admin.

### LLM
 - Optional. Local only (Ollama, llama.cpp). The admin sets the server address.
 - Output in ASD-STE100.

### Not in P0
 - More than one host. Keep the architecture open for it.
 - Registry access, log storage, container actions, host metrics, alerts when WT itself stops. (WT watches its own container like all other containers.)

### P1 (future)
 - Read Home Assistant logs on other machines (RPi5).
 - Home Assistant: Matter/Thread log analysis, anomalies, device offline alerts.
 - App traffic monitoring.
 - Home network via UniFi: devices, new device permissions, anomalies.
 - Traefik integration (routes, access logs).
 - Fix issues (container actions).

## Engineering principles

1. Use simple logic. Do not add abstractions that you do not need.
2. Keep the code modular and easy to change.
3. Use strong types. Document the code.
4. Write all text, messages and comments in ASD-STE100.
5. Build only what P0 needs. Design the architecture for the future scope.
6. Design for home-lab scale: 1 admin, 10s of machines, 100s of apps.
7. Thin frontend. The backend makes all decisions (status, grouping, labels, validation). The frontend shows what the API sends. Exception: log search and JSON pretty-print run in the browser.

## Design

### Overview

```
Browser / PWA --HTTPS--> Traefik --HTTP--> WT container
                                           |- React app (static files)
                                           |- FastAPI: REST + SSE
                                           |- Workers: Docker events, version check, cleanup
                                           '- SQLite (/data/wt.db)
WT --HTTP--> socket-proxy (GET only) --> Docker
WT --HTTPS--> GitHub API, ntfy, LLM server
```

One process runs the API and the workers. Uvicorn runs 1 worker, because the workers keep state in memory.

### Stack

| Area | Choice | Why | Other options |
|---|---|---|---|
| Backend | Python 3.14, FastAPI, Uvicorn | Fast to write. Good LLM libraries. ~80-120 MB RAM. | Go (less RAM), TypeScript, Rust |
| Docker client | aiodocker | Async streams for logs and events. Typed. | docker-py (blocking) |
| Socket proxy | linuxserver/socket-proxy | Maintained Tecnativa fork. `POST=0` makes it read-only. | Tecnativa, wollomatic |
| Database | SQLite (WAL) | One file. No server. | Postgres (too large) |
| DB layer | SQLModel + Alembic | One class is the table and the Pydantic model. | SQLAlchemy 2, raw SQL |
| API | REST, OpenAPI from FastAPI | One source of truth for types. | Hand-written types, Connect RPC |
| TS types | openapi-typescript + openapi-fetch | One types file. Small fetch client. | Hey API |
| Live data | SSE | One-way. Plain HTTP. Works behind any proxy. Auto reconnect. | WebSocket |
| TOTP QR code | segno | Pure Python, no deps. Gives SVG. | qrcode (npm) |
| Scheduler | asyncio task loop | No library. One job type. | APScheduler |
| HTTP client | httpx (async) | Standard for async Python. | aiohttp |
| Frontend | React 19, Vite, TypeScript (strict) | Largest ecosystem. Easy path to a native app. | Svelte 5, Vue 3 |
| UI | Tailwind CSS, shadcn/ui | Copy-in components. No large UI kit. | MUI, Mantine |
| Data fetch | TanStack Query | Cache, refetch, loading state. | SWR |
| Routing | React Router | Standard. | TanStack Router |
| Log view | TanStack Virtual | 10,000 lines with no lag. | react-virtuoso |
| PWA | vite-plugin-pwa | Manifest and service worker. | Manual service worker |
| Tooling | uv, ruff, pyright (strict); pnpm, ESLint | Current standard tools. | poetry, mypy |
| Tests | pytest, pytest-cov, Hypothesis, respx, testcontainers; Vitest, jsdom, @vitest/coverage-v8, Testing Library, MSW; Playwright, @axe-core/playwright | See Tests. | Jest, Cypress |

### Repository

 - Source: https://github.com/yash91sharma/watch-tower (public). Default branch: `main`.
 - Image: `ghcr.io/yash91sharma/watch-tower`. Tags: version (`0.0.0`) and `latest`.
 - No CI/CD for now. The pre-commit hook runs `check.sh`. Docker, E2E, image, mutation, footprint and LLM eval tests run by hand in `wt_dev`.
 - Releases: tag `v*`, then build and push the image by hand (`docker buildx`, both architectures).

### Code layout

```
backend/wt/
  main.py        app and worker start
  cli.py         wt command: serve, reset-admin, openapi
  config.py      env vars (pydantic-settings), UI settings
  clock.py       the only source of the current time
  bus.py         in-process event bus
  db/            SQLModel tables, Alembic migrations
  docker/        all Docker API calls (the only module that uses Docker)
  versions/      GitHub fetch, version rule, release notes
  health/        event rules, restart window
  notify/        ntfy messages and digest
  llm/           update summary
  auth/          password, TOTP, sessions, admin reset
  api/           routes, SSE
backend/tests/   unit/, integration/, contract/
frontend/src/    React app, *.test.tsx next to each component
e2e/             Playwright specs, compose.test.yaml, fakes/ (GitHub, LLM, test containers)
Dockerfile, compose.yaml
```

### Data model

Host data links to a `host` row: `container` has a `host_id`, and `update` and `event` link to `container`. P0 has one host row. This keeps multi-host open.

The container key is (`host_id`, name). Compose makes a new Docker id on each recreate. The name keeps admin values and links stable. URLs use the name.

| Table | Content |
|---|---|
| `host` | id, name |
| `container` | Docker id, name, Compose project, image, tag, enabled, release source, source confirmed |
| `repo_cache` | repo, ETag, latest tag, release list, fetch time, last error |
| `update` | container, from version, to version, severity, summary, release notes, notified time |
| `event` | container, kind (a health state change, see Health), time. Kept 7 days. |
| `setting` | key, value |
| `admin` | id, password hash, TOTP secret, last TOTP step |
| `session` | token hash, created, expires, last seen |

### Docker access

 - WT uses `DOCKER_HOST=tcp://socket-proxy:2375`.
 - The proxy allows only GET on `_ping`, `version`, `containers`, `events` and container logs (`ALLOW_LOGS=1`).
 - At start, WT lists all containers. Then WT reads the `events` stream for start, die, health status and destroy.
 - If the stream stops, WT connects again with backoff and lists all containers again.
 - The Compose project comes from the label `com.docker.compose.project`.

### Version check

1. Read the release source from the image label `org.opencontainers.image.source`. Use it only if it is a `github.com` URL. The admin can set or change it.
2. `GET /repos/{owner}/{repo}/releases/latest` with `If-None-Match` (ETag). Containers with the same repo share one call.
3. Apply the update rule.
4. For release notes, get one page of `/releases?per_page=100`. Keep the releases after the running version, up to the latest. When the running version changes, WT makes the notes, severity and summary again.
5. Rate limit: 60 calls/hour with no token, 5,000 with a token. At the limit, WT waits until the reset time.
6. A failed fetch, or a latest tag that is not a version, saves the error in `repo_cache`. The UI shows status "error".

### Update summary (LLM)

 - WT calls `POST {llm_url}/v1/chat/completions` (Ollama, llama.cpp and LM Studio support it).
 - WT sends `response_format` with a JSON schema: `{severity: "critical" | "normal", summary: string}`.
 - The prompt asks for a summary in ASD-STE100, max 2 sentences.
 - Timeout 60 s. On error, WT shows the release notes only.
 - Without an LLM: severity is critical if the notes contain `CVE-` or `security`. Else normal.

### Health

 - Unhealthy: event `health_status: unhealthy`.
 - Restart loop: N or more `start` events after `die` in M minutes. Default N=3, M=10.
 - Recovery: `health_status: healthy` after unhealthy, or no restart in M minutes after a loop.
 - State changes: became unhealthy, recovered health, restart loop, recovered loop. WT sends one notification and saves one `event` row per state change.
 - At start and after a resync, WT reads the state and sends no notification.

### Logs

 - `GET /api/containers/{name}/logs` is an SSE stream. Parameters: `tail` (default 500), `follow`, `since`.
 - Each line is one event: time, stream (stdout or stderr), text.
 - The browser keeps max 10,000 lines. Search and JSON pretty-print run in the browser.
 - Download: `GET /api/containers/{name}/logs.txt` streams the full log, with no follow.

### Live updates

 - `GET /api/stream` is one SSE stream for container state, check status and Docker connection state. The event bus feeds it. On connect, it first sends the current Docker connection state.
 - After a reconnect, the UI gets all data again.

### Notifications (ntfy)

 - `POST {ntfy_url}/{topic}` with headers `Title`, `Priority`, `Tags`, `Click` (link to WT).
 - Priority: `high` for critical updates and unhealthy containers. `default` for all other messages.
 - After each check run, WT sends one message for one update, or one digest for more.
 - WT stores the notified time per update and sends each version once.

### Auth design

 - Start with no admin: WT writes a one-time setup token to its log. The setup page asks for the token, a password and a TOTP code.
 - Password hash: Argon2id (argon2-cffi), OWASP minimum: 19 MiB memory, 2 iterations, 1 lane.
 - TOTP: pyotp, 30 s step, ±1 step window. WT rejects a step that it accepted before (replay).
 - Session: random token in a cookie (`HttpOnly`, `Secure`, `SameSite=Strict`). WT stores the token hash. Expires after 30 days with no use.
 - Login limit: after 5 failed attempts, wait 15 minutes.
 - Reset: `docker exec wt wt reset-admin` deletes the password, TOTP and sessions. Then `docker restart wt` clears the state in memory and writes a new setup token. The next visit shows the setup page.

### Config and secrets

 - Env vars hold secrets and deploy values. Each secret also accepts `<NAME>_FILE` (Docker secrets).
   - `DOCKER_HOST`, `WT_DATA_DIR`, `WT_TRUSTED_PROXIES`, `WT_LOG_LEVEL`
   - `WT_GITHUB_API_URL` (default `https://api.github.com`). Tests set it to the fake GitHub.
   - Secrets: `WT_GITHUB_TOKEN`, `WT_NTFY_TOKEN`, `WT_LLM_API_KEY`
 - The UI holds all other settings: check interval (default 24 h), N and M, ntfy URL and topic, LLM URL and model, WT public URL.
 - The UI shows each secret as "set" or "not set".
 - Export and import use JSON: settings and per-container values. Export has no secrets.

### Reverse proxy

 - WT reads `X-Forwarded-*` headers only from `WT_TRUSTED_PROXIES`.
 - WT serves at the root path of its host name (for example `wt.example.com`). No sub-path in P0.

### Deploy

 - One image, multi-stage build: Node builds the frontend, `python:3.14-slim` runs the backend. FastAPI serves the static files.
 - Multi-arch: `linux/arm64` and `linux/amd64`. Built and pushed to GHCR by hand.
 - Non-root user, `no-new-privileges`, read-only root filesystem. Writable: `/data` and a `/tmp` tmpfs.
 - Healthcheck: `GET /api/health` (no auth).
 - The socket proxy is on an internal network with no published port.
 - Backup: stop WT, copy the `wt-data` volume, start WT. (A copy of `wt.db` alone while WT runs can lose WAL data.)

```yaml
services:
  socket-proxy:
    image: lscr.io/linuxserver/socket-proxy
    environment: [CONTAINERS=1, EVENTS=1, ALLOW_LOGS=1, POST=0]
    volumes: [/var/run/docker.sock:/var/run/docker.sock:ro]
    read_only: true
    tmpfs: [/run]
    networks: [docker]
  wt:
    image: ghcr.io/yash91sharma/watch-tower
    container_name: wt
    environment:
      DOCKER_HOST: tcp://socket-proxy:2375
      WT_TRUSTED_PROXIES: <traefik ip>
    env_file: .env          # secrets
    volumes: [wt-data:/data]
    read_only: true
    tmpfs: [/tmp]
    security_opt: [no-new-privileges:true]
    mem_limit: 256m
    cpus: 0.5
    networks: [docker, default]
networks:
  docker:
    internal: true
volumes:
  wt-data:
```

### Tests

Each feature has tests at all levels. A pull request merges only if all PR checks pass.

**Testability rules**
 - Code gets the time only from `wt/clock.py`. Tests set the time (restart window, TOTP, session expiry).
 - All external URLs come from config (GitHub, ntfy, LLM). Tests point them to fakes.
 - Tests do not call the real GitHub, ntfy or LLM. Exception: the LLM eval (run by hand).

**Test types**

| Type | Tools | Covers |
|---|---|---|
| Static | ruff, pyright (strict), ESLint, `tsc --strict` | Lint, format, types. ruff `S` rules for security. |
| Unit | pytest | Version rule, tag filter, release range, Compose grouping, severity keywords, restart window, health state changes, digest, message text, label parse, config parse, password hash, TOTP replay, login limit. |
| Property | Hypothesis | Version rule and release range with random tags. No crash. Same input gives same result. |
| Integration | pytest, httpx, respx, temp SQLite | All API routes with a real DB. respx mocks GitHub, ntfy and LLM: ETag 304, rate limit 403, timeout, bad JSON. |
| Docker | testcontainers, real Docker + socket proxy | Container list, Compose groups, `wt.enable=false`, events stream, proxy restart and sync, log stream and download. Test containers: healthy, unhealthy, restart loop, JSON logs, TTY. They start healthy. Tests cause failures with `docker exec`. |
| Migration | pytest, Alembic | Upgrade from empty to head. Upgrade with data from the last release. `alembic check` finds no model drift. |
| Contract | schemathesis, OpenAPI diff | Fuzz all routes from the OpenAPI schema: no 500 errors. Generated TS types match the committed file. |
| Auth | pytest | All routes except `/api/health` and auth routes give 401 with no session. Cookie flags. Session expiry. Setup token single use. Admin reset. |
| Frontend unit | Vitest, Testing Library, MSW | Components, hooks, log parse, search, JSON pretty-print, error and empty states. |
| E2E | Playwright | Full stack from `compose.test.yaml`. See E2E flows. |
| Accessibility | @axe-core/playwright | No serious or critical issues on any page. |
| Visual | Playwright screenshots | Main pages at desktop and phone width, light and dark mode. |
| PWA | Playwright | Valid manifest. Service worker registers. App shell loads offline. `/api` is not cached. |
| Image | Trivy, pytest | No high or critical CVEs. Non-root user. Healthcheck passes. Both architectures start. |
| Dependencies | pip-audit, `pnpm audit` | No known vulnerable packages. |
| Footprint | pytest, `docker stats` | Idle RAM < 200 MB with 50 test containers. After 5 s of a log stream at 1,000 lines/s, a click on pause updates the UI in < 200 ms. |
| Mutation | mutmut | Rule modules (`versions/`, `health/`, `notify/`). Score ≥ 80%. |
| LLM eval | pytest, real Ollama | 20 known release notes. Severity matches the expected value. The reply matches the schema. |

**E2E stack** (`compose.test.yaml`): WT, socket proxy, Traefik with a self-signed certificate (browsers need HTTPS for `Secure` cookies), ntfy server, fake GitHub API, fake LLM API, test containers (healthy, unhealthy, restart loop, `latest` tag, excluded, JSON logs). Playwright runs in the official Playwright image with the Docker CLI added. Support services have `wt.enable=false`. Tests check only the E2E Compose project. Fake GitHub starts with no updates. Each flow adds its releases.

**Pre-commit** runs static checks and all tests except Docker, E2E and LLM eval. The other tests run by hand (no CI for now).

**E2E flows**
1. Setup: read the token from the WT log, set the password, scan TOTP (the test computes the code).
2. Login, logout, wrong password, wrong TOTP, login limit (then restart WT), session expiry.
3. Container list: Compose groups, excluded container not shown, `latest` shows "no check".
4. Release source: value from the label, admin edits and confirms it.
5. Check now: the update shows versions, notes and summary. ntfy gets one message with a WT link. A second run sends nothing.
6. Two updates: ntfy gets one digest. A critical update gives high priority.
7. LLM off and LLM timeout: notes only, keyword severity.
8. Health: unhealthy, restart loop and recovery each send one ntfy message.
9. Logs: live tail, search, JSON pretty-print, download.
10. Settings: change values, export, import into a clean WT (delete the DB, restart WT, set up).
11. Admin reset: `docker exec wt wt reset-admin`, `docker restart wt`, then the setup page.
12. Docker stream stops (restart the socket proxy): the UI recovers, no false notifications.

Flows 1-12 run once on Chromium at desktop size, because they change WT state. A read-only smoke spec, accessibility and visual tests run on Chromium and WebKit (Safari engine), at desktop, iPhone and Pixel sizes.

**Coverage gates**
 - Backend: ≥ 90% line and branch. Rule modules: 100% branch.
 - Frontend: ≥ 85% line and branch.
 - Each requirement has at least one E2E flow.

**By hand** (in `wt_dev`; no CI for now)
 - Docker and image: `cd backend && uv run pytest -m docker -n0`
 - E2E, accessibility, visual, PWA: `bash e2e/run.sh`
 - Footprint: `FOOTPRINT=1 bash e2e/run.sh --project footprint`
 - Mutation: `bash .devcontainer/mutation.sh`
 - LLM eval (needs Ollama): `cd backend && uv run pytest -m llm_eval -n0`
 - Dependencies: `cd backend && uv run pip-audit --skip-editable`; `pnpm audit --audit-level high` in `frontend/` and `e2e/`

### Future: multi-host

 - Only `wt/docker/` talks to Docker. Later, an agent on each host gives the same calls over the network.
 - The agent connects out to WT over WebSocket (the Beszel model). No host must open a port.
