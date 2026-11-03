# Playwright runner for the E2E tests (task 16.5). The image tag matches @playwright/test.
# It has the Docker CLI: the helpers read the WT log and restart containers.
FROM docker:29.9.2-cli AS docker

FROM mcr.microsoft.com/playwright:v1.64.1-noble
ARG PNPM_VERSION=12.16.1
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
RUN npm install -g pnpm@${PNPM_VERSION} && npm cache clean --force
WORKDIR /e2e
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm typecheck
ENTRYPOINT ["pnpm", "exec", "playwright", "test"]
