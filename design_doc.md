## Objective

Watch Tower (WT) is an application for a home lab server. WT watches the setup, traffic, devices and apps. WT finds issues, anomalies and risks, and flags them. In the future, WT will also fix them.

WT runs on the home server. WT connects to apps on the same Docker host, the same machine and the same network.

### Non-goals
 - WT does not watch individual apps for what they are doing or how they process data
 - WT does not optimize individual apps for efficiency, optimizations etc

## Requirements

### P0: monitoring only

P0 is read-only. WT does not act on containers.

#### Containers
 - WT watches all containers on the host. Label `wt.enable=false` excludes a container.
 - The UI groups containers by Compose project. Checks and notifications are per container. Containers started via same docker-compose file should be grouped together.
 - Docker access goes through a read-only socket proxy.

#### Version check
 - Running version: the image tag.
 - Latest version: the latest GitHub release of the release source. GitHub excludes drafts and pre-releases from "latest".
 - Release source: WT finds it from the image label `org.opencontainers.image.source`. The admin confirms or edits it in the UI.
 - Update rule: remove a leading `v` and any `-suffix` from both versions. Update if they differ, unless the running tag is a short form of the latest (`16` matches `16.4.1`).
 - Tags that are not versions (`latest`, `stable`, `main`, digest only) get no check. The UI shows "no check".
 - Runs every X hours (configurable) and on "Check now".
 - Optional GitHub token for API rate limits.

#### Update summary
 - Shows running version, latest version and the release notes between them.
 - Optional LLM summary, 1-2 lines: critical (CVE, security fix) or normal (features, fixes).
 - Without an LLM, shows the release notes only.

#### Health
 - Shows container state and healthcheck status.
 - Notifies when a container becomes unhealthy, restarts N times in M minutes, or recovers.

#### Logs (like [Dozzle](https://github.com/amir20/dozzle))
 - Live tail, search, JSON pretty-print, download.
 - Streams from the Docker API. No log storage.

#### Notifications (ntfy)
 - Public or private ntfy server, optional token.
 - One update found: one message. More than one: one digest.
 - Each version is notified once. Critical updates use high priority.
 - Messages are short and link to WT.

### Platform
 - One container: frontend, backend, SQLite.
 - Deploy with docker-compose and env vars. Per-container rules use Docker labels. Other settings are in the UI. Config export/import.
 - Prod: OrbStack on macOS (M2). Dev: Docker on macOS.
 - Clients: web app and PWA (Android, iOS, iPadOS). Native Android app possible later.
 - Access: Tailscale -> Traefik -> WT. Cloudflare for DNS and TLS, terminated at Traefik. WT must work behind any reverse proxy.
 - Small footprint: < 200 MB RAM idle. CPU and memory limits in the compose file.

### Auth
 - One admin user. Password and TOTP.
 - No other users, no SSO. No self-service recovery. Host access can reset the admin (see Auth design).

### LLM
 - Optional. Local only (Ollama, llama.cpp etc). The admin sets the server address.
 - Output in ASD-STE100.

### Not in P0
 - More than one host. Keep the architecture open for it.
 - Registry access, log storage, container actions, host metrics, monitoring of WT itself.

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
6. Design for home-lab scale: 1 admin, 10s of machines, 100s of apps at max.

## Design

### Overview

```
Browser / PWA --HTTPS--> Traefik --HTTP--> WT container
                                           |- React app (static files)
                                           |- FastAPI: REST + SSE
                                           |- Workers: Docker events, version check
                                           '- SQLite (/data/wt.db)
WT --HTTP--> socket-proxy (GET only) --> Docker
WT --HTTPS--> GitHub API, ntfy, LLM server
```

One process runs the API and the workers. Uvicorn runs with 1 worker, because the workers keep state in memory.

### Stack

| Area | Choice | Why | Other options |
|---|---|---|---|
| Backend | Python 3.14, FastAPI, Uvicorn | Fast to write. Good LLM libraries. ~80-120 MB RAM. | Go (less RAM), TypeScript, Rust |
| Docker client | aiodocker | Async streams for logs and events. Typed. | docker-py (blocking, needs threads) |
| Socket proxy | linuxserver/socket-proxy | Maintained Tecnativa fork. Same env vars. `POST=0` makes it read-only. | Tecnativa, wollomatic (regex rules) |
| Database | SQLite (WAL mode) | One file. No server. Enough for one host. | Postgres (too large) |
| DB layer | SQLModel + Alembic | One class is the table and the Pydantic model. | SQLAlchemy 2, raw SQL |
| API | REST, OpenAPI from FastAPI | One source of truth for types. | Hand-written types, Connect RPC |
| TS types | openapi-typescript + openapi-fetch | One types file. Small fetch client. | Hey API (more generated files) |
| Live data | SSE | One-way. Plain HTTP. Works behind any proxy. Auto reconnect. | WebSocket (two-way, not needed) |
| Scheduler | asyncio task loop | No library. One job type. | APScheduler |
| HTTP client | httpx (async) | Standard for async Python. | aiohttp |
| Frontend | React 19, Vite, TypeScript (strict) | Largest ecosystem. Easy path to a native app. | Svelte 5, Vue 3 |
| UI | Tailwind CSS, shadcn/ui | Copy-in components. No large UI kit. | MUI, Mantine |
| Data fetch | TanStack Query | Cache, refetch, loading state. | SWR |
| Routing | React Router | Standard. Small app. | TanStack Router |
| Log view | TanStack Virtual | Shows 10,000 lines without lag. | react-virtuoso |
| PWA | vite-plugin-pwa | Manifest and service worker. App shell cache only. | Manual service worker |
| Tooling | uv, ruff, pyright (strict); pnpm, ESLint | Current standard tools. | poetry, mypy |
| Tests | pytest, Hypothesis, respx, testcontainers; Vitest, Testing Library, MSW; Playwright | See Tests. | Jest, Cypress |

### Repository

 - Source: https://github.com/yash91sharma/watch-tower (public). Default branch: `main`.
 - Image: `ghcr.io/yash91sharma/watch-tower`. Tags: version (`0.1.0`) and `latest`.
 - Releases: Git tag `v*` starts the image build. Each release has GitHub release notes.
 - `main` is protected. Changes go in through pull requests. All PR checks must pass (see Tests).
 - Dependabot updates Python, npm, GitHub Actions and Docker base images.

### Code layout

```
backend/wt/
  main.py        app start, worker start
  config.py      env vars (pydantic-settings)
  db/            SQLModel tables, Alembic migrations
  docker/        all Docker API calls (the only module that uses Docker)
  versions/      GitHub fetch, version rule, release notes
  health/        event rules, restart window
  notify/        ntfy messages and digest
  llm/           update summary
  auth/          password, TOTP, sessions, CLI reset
  api/           routes, SSE
  clock.py       the only source of the current time
backend/tests/   unit/, integration/, contract/
frontend/src/    React app, *.test.tsx next to each component
e2e/             Playwright specs, compose.test.yaml, fakes/ (GitHub, LLM)
Dockerfile, compose.yaml, .github/workflows/
```

### Data model

All tables that hold host data have a `host_id`. P0 has one host row. This keeps multi-host open.

| Table | Content |
|---|---|
| `host` | id, name |
| `container` | Docker id, name, Compose project, image, tag, enabled, release source, source confirmed |
| `repo_cache` | repo, ETag, latest tag, release list, fetch time |
| `update` | container, from version, to version, severity, summary, notified time |
| `event` | container, kind (unhealthy, healthy, restart), time. Kept 7 days. |
| `setting` | key, value |
| `admin` | password hash, TOTP secret, last TOTP step |
| `session` | token hash, created, expires, last seen |

### Docker access

 - WT uses `DOCKER_HOST=tcp://socket-proxy:2375`.
 - The proxy allows only GET on: `_ping`, `version`, `info`, `containers`, `images`, `events`, container logs (`ALLOW_LOGS=1`).
 - At start, WT lists all containers. Then WT reads the `events` stream for start, die, health status, destroy.
 - If the stream stops, WT connects again with backoff. Then WT lists all containers again to sync.
 - Compose project comes from label `com.docker.compose.project`.

### Version check

1. Read the release source from the image label `org.opencontainers.image.source`. Use it only if it is a `github.com` URL. The admin can set or change it.
2. Get `GET /repos/{owner}/{repo}/releases/latest` with `If-None-Match` (ETag). Containers with the same repo use one call.
3. Apply the update rule (see Requirements).
4. For release notes, get one page of `/releases?per_page=100`. Keep the releases after the running version, up to the latest.
5. Rate limit: 60 calls/hour without a token, 5,000 with a token. On the limit, WT waits until the reset time.

### Update summary (LLM)

 - WT calls `POST {llm_url}/v1/chat/completions`. Ollama, llama.cpp and LM Studio support this API.
 - WT sends `response_format` with a JSON schema: `{severity: "critical" | "normal", summary: string}`.
 - The prompt tells the model to write the summary in ASD-STE100, max 2 sentences.
 - Timeout 60 s. On error, WT shows the release notes only.
 - Without an LLM: severity is critical if the notes contain `CVE-` or `security`. Else normal.

### Health

 - Unhealthy: event `health_status: unhealthy`.
 - Restart loop: N or more `start` events after `die` in M minutes. Default N=3, M=10.
 - Recover: `health_status: healthy` after unhealthy, or no restart in M minutes after a loop.
 - WT sends one notification per state change. At WT start, WT reads the state and sends no notification.

### Logs

 - `GET /api/containers/{id}/logs` is an SSE stream. Parameters: `tail` (default 500), `follow`, `since`.
 - Each line is one event: time, stream (stdout or stderr), text.
 - The browser keeps max 10,000 lines. Search and JSON pretty-print run in the browser.
 - Download: `GET /api/containers/{id}/logs.txt`. It streams the full log, without follow.

### Notifications (ntfy)

 - `POST {ntfy_url}/{topic}` with headers `Title`, `Priority`, `Tags`, `Click` (link to WT).
 - Priority: `high` for critical updates and unhealthy containers. `default` for all other messages.
 - After each check run, WT sends one message for one update, or one digest for more.
 - WT stores `notified time` per update. WT sends each version once.

### Auth design

 - First start: WT writes a one-time setup token to its log. The setup page asks for the token, a password and a TOTP code.
 - Password hash: Argon2id (argon2-cffi). OWASP minimum: 19 MiB memory, 2 iterations, 1 lane.
 - TOTP: pyotp, 30 s step, ±1 step window. WT rejects a step that it accepted before (replay).
 - Session: random token in a cookie (`HttpOnly`, `Secure`, `SameSite=Strict`). WT stores the token hash. Expires after 30 days without use.
 - Login limit: after 5 failed attempts, wait 15 minutes.
 - Reset: `docker exec wt wt reset-admin` deletes the password, TOTP and sessions. The next open shows the setup page.

### Config and secrets

 - Env vars hold secrets and deploy values. Each secret also accepts `<NAME>_FILE` (Docker secrets).
   - `DOCKER_HOST`, `WT_DATA_DIR`, `WT_TRUSTED_PROXIES`, `WT_LOG_LEVEL`
   - `WT_GITHUB_API_URL` (default `https://api.github.com`). Tests set it to the fake GitHub.
   - Secrets: `WT_GITHUB_TOKEN`, `WT_NTFY_TOKEN`, `WT_LLM_API_KEY`
 - The UI holds all other settings: check interval (default 24 h), N and M, ntfy URL and topic, LLM URL and model, WT public URL.
 - The UI shows each secret as "set" or "not set".
 - Export and import are JSON: settings and per-container values. Export has no secrets.

### Reverse proxy

 - WT reads `X-Forwarded-*` headers only from `WT_TRUSTED_PROXIES`.
 - WT serves at the root path of its host name (for example `wt.example.com`). P0 does not support a sub-path.

### Deploy

 - One image, multi-stage build: Node builds the frontend, then `python:3.14-slim` runs the backend. FastAPI serves the static files.
 - Multi-arch: `linux/arm64` and `linux/amd64`. GitHub Actions builds and pushes to GHCR.
 - The container runs as non-root, with `no-new-privileges`. Only `/data` is writable.
 - Healthcheck: `GET /api/health` (no auth).
 - Compose limits: `mem_limit: 256m`, `cpus: 0.5`.

```yaml
services:
  socket-proxy:
    image: lscr.io/linuxserver/socket-proxy
    environment: [CONTAINERS=1, IMAGES=1, INFO=1, EVENTS=1, ALLOW_LOGS=1, POST=0]
    volumes: [/var/run/docker.sock:/var/run/docker.sock:ro]
    read_only: true
    tmpfs: [/run]
  wt:
    image: ghcr.io/yash91sharma/watch-tower
    environment:
      DOCKER_HOST: tcp://socket-proxy:2375
      WT_TRUSTED_PROXIES: <traefik ip>
    env_file: .env          # secrets
    volumes: [wt-data:/data]
    mem_limit: 256m
    cpus: 0.5
volumes:
  wt-data:
```

### Tests

Each feature has tests at all levels. A pull request merges only if all PR checks pass.

**Testability rules**
 - Code gets the time only from `wt/clock.py`. Tests set the time (restart window, TOTP, session expiry).
 - All external URLs come from config (GitHub, ntfy, LLM). Tests point them to fakes.
 - Tests do not call the real GitHub, ntfy or LLM, except the nightly LLM eval.

**Test types**

| Type | Tools | Covers |
|---|---|---|
| Static | ruff, pyright (strict), ESLint, `tsc --strict` | Lint, format, types. ruff `S` rules for security. |
| Unit | pytest | Version rule, tag filter, release range, severity keywords, restart window, health state changes, digest, message text, label parse, config parse, password hash, TOTP replay, login limit. |
| Property | Hypothesis | Version rule and release range with random tags. No crash. Same input gives same result. |
| Integration | pytest, httpx, respx, temp SQLite | All API routes with a real DB. GitHub, ntfy and LLM mocked with respx: ETag 304, rate limit 403, timeout, bad JSON. |
| Docker | testcontainers, real Docker + socket proxy | Container list, Compose groups, `wt.enable=false`, events stream, proxy restart and sync, log stream and download. Test containers: healthy, unhealthy, restart loop, JSON logs. |
| Migration | pytest, Alembic | Upgrade from empty to head. Upgrade with data from the last release. `alembic check` finds no model drift. |
| Contract | schemathesis, OpenAPI diff | Fuzz all routes from the OpenAPI schema: no 500 errors. Generated TS types match the committed file. |
| Auth | pytest | Every route except `/api/health` and auth routes returns 401 without a session. Cookie flags. Session expiry. Setup token single use. CLI reset. |
| Frontend unit | Vitest, Testing Library, MSW | Components, hooks, log parse, search, JSON pretty-print, Compose grouping, error and empty states. |
| E2E | Playwright | Full stack from `compose.test.yaml`. See E2E flows. |
| Accessibility | axe-core (in Playwright) | Each page has no serious or critical issues. |
| Visual | Playwright screenshots | Main pages on desktop and phone width, light and dark mode. |
| PWA | Playwright, Lighthouse CI | Manifest is valid. Service worker registers. App shell loads offline. |
| Image | Trivy, Playwright | No high or critical CVEs. Container runs as non-root. Healthcheck passes. Both architectures start. |
| Dependencies | pip-audit, `pnpm audit`, Dependabot | No known vulnerable packages. |
| Footprint | pytest + `docker stats` | Idle RAM < 200 MB with 50 test containers. Log stream of 1,000 lines/s does not lag. |
| Mutation | mutmut | Rule modules (`versions/`, `health/`, `notify/`). Score ≥ 80%. |
| LLM eval | pytest, real Ollama, Stelint | 20 known release notes. Severity matches the expected value. Summary passes the STE check. |

**E2E stack** (`compose.test.yaml`): WT, socket proxy, real ntfy server, fake GitHub API, fake LLM API, test containers (healthy, unhealthy, restart loop, `latest` tag, excluded, JSON logs).

**E2E flows**
1. Setup: read the token from the WT log, set the password, scan TOTP (the test computes the code).
2. Login, logout, wrong password, wrong TOTP, login limit, session expiry.
3. Container list: Compose groups, excluded container is not shown, `latest` shows "no check".
4. Release source: auto value from label, admin edits and confirms it.
5. Check now: update shows versions, notes and summary. ntfy gets one message. Run again: no new message.
6. Two updates: ntfy gets one digest. Critical update has high priority.
7. LLM off and LLM timeout: notes only, keyword severity.
8. Health: unhealthy, restart loop and recover each send one ntfy message.
9. Logs: live tail, search, JSON pretty-print, download.
10. Settings: change values, export, import into a clean WT.
11. CLI reset: `docker exec wt wt reset-admin`, then setup page.
12. Docker stream stops (restart socket proxy): UI recovers, no false notifications.

E2E runs on Chromium and WebKit (Safari engine), at desktop, iPhone and Pixel sizes.

**Coverage gates**
 - Backend: ≥ 90% line and branch. Rule modules: 100% branch.
 - Frontend: ≥ 85% line and branch.
 - Each requirement has at least one E2E flow.

**CI**
 - Each PR: static, unit, property, integration, Docker, migration, contract, auth, frontend unit, E2E, accessibility, visual, PWA, image, dependencies.
 - Nightly: mutation, LLM eval, footprint, long schemathesis run.

### Future: multi-host

 - Only `wt/docker/` talks to Docker. A later agent on each host gives the same calls over the network.
 - The agent connects out to WT over WebSocket (the Beszel model). Then no host must open a port.
