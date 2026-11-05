# Dev image: Python 3.15 + uv, Node 26 + pnpm, Docker CLI.
# Pinned tool versions.
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM docker:29.9.3-cli AS docker
FROM node:26.13.0-trixie-slim AS node

FROM python:3.15.2-slim-trixie

ARG PNPM_VERSION=12.16.1
ARG USERNAME=dev
ARG USER_UID=1000

# Node 26 needs libatomic1.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates sudo libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g pnpm@${PNPM_VERSION} \
    && npm cache clean --force

# Non-root user in the docker group. post-start.sh gives the socket to that group.
RUN groupadd docker \
    && useradd -m -u ${USER_UID} -G docker -s /bin/bash ${USERNAME} \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME} \
    # Make the mount points for the cache volumes, so that the volumes belong to the user.
    && mkdir -p /home/${USERNAME}/.cache/uv /home/${USERNAME}/.local/share/pnpm \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

USER ${USERNAME}
