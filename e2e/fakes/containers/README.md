# Test containers

`app/` is a busybox app for the Docker tests (`backend/tests/docker/`) and the E2E tests.
`backend/tests/docker/conftest.py` builds it and starts the `wt_test_*` containers.

- Healthy while `/tmp/ok` exists. Make it unhealthy: `docker exec <name> rm /tmp/ok`.
- Crash K times: `docker exec <name> sh -c 'echo K > /tmp/crash'` (the container has `restart: on-failure`).
- `MODE=json` writes JSON lines to stdout and plain lines to stderr.

Each test sets its container back to healthy at the end (`touch /tmp/ok`, `rm -f /tmp/crash`).
