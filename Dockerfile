# WT image. Node builds the frontend. python:3.14-slim runs the backend and serves the
# frontend files. Pinned base images (Dependabot updates them).
# Build: docker build --build-arg VERSION=0.0.0 --build-arg REVISION=$(git rev-parse HEAD) .
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

FROM node:24.22.2-trixie-slim AS frontend
ARG PNPM_VERSION=12.16.1
RUN npm install -g pnpm@${PNPM_VERSION} && npm cache clean --force
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.14.10-slim-trixie AS backend
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Deps first, so that a code change does not install them again.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/wt ./wt
COPY --from=frontend /frontend/dist ./wt/static
# The root filesystem is read-only at run time, so compile the WT code here too.
RUN uv sync --frozen --no-dev && python -m compileall -q wt

FROM python:3.14.10-slim-trixie
ARG VERSION=0.0.0
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/yash91sharma/watch-tower" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
# WT does not need pip at run time. Its vendored packages (urllib3, msgpack) had CVEs.
RUN python -m pip uninstall --yes --quiet pip \
    && useradd --system --user-group --uid 10001 --no-create-home --home-dir /nonexistent wt \
    && install -d -o wt -g wt -m 700 /data
COPY --from=backend /app /app
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER wt
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
ENTRYPOINT ["wt"]
CMD ["serve"]
