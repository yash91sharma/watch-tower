# WT image. Node builds the frontend. python:3.15-slim runs the backend and serves the
# frontend files. Pinned base images.
# Build: docker build --build-arg VERSION=0.0.0 --build-arg REVISION=$(git rev-parse HEAD) .
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

FROM node:26.13.0-trixie-slim AS frontend
ARG PNPM_VERSION=12.16.1
RUN npm install -g pnpm@${PNPM_VERSION} && npm cache clean --force
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.15.2-slim-trixie AS backend
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Deps first, so that a code change does not install them again.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/wt ./wt
COPY --from=frontend /frontend/dist ./wt/static
# Install WT as a normal package (not editable), so that the final image needs only the venv.
# UV_COMPILE_BYTECODE compiles WT too, because the root filesystem is read-only at run time.
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.15.2-slim-trixie
ARG VERSION=0.0.0
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/yash91sharma/watch-tower" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
# Install the Debian security fixes that the base image does not have yet (for example,
# zlib1g CVE-2026-76844 and CVE-2026-85091).
# WT does not need pip or the ensurepip wheel at run time. Their vendored packages
# (urllib3, msgpack) had CVEs.
RUN apt-get update \
    && apt-get upgrade --yes --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes --quiet pip \
    && rm -rf /usr/local/lib/python3.15/ensurepip \
    && useradd --system --user-group --uid 10001 --no-create-home --home-dir /nonexistent wt \
    && install -d -o wt -g wt -m 700 /data
COPY --from=backend /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER wt
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
ENTRYPOINT ["wt"]
CMD ["serve"]
