# Watch Tower

Watch Tower (WT) watches the Docker containers of a home-lab server. It shows the state and the health of each container. It finds new versions on GitHub and tells you which updates are important. It sends notifications to ntfy. It shows the live logs.

WT is for 1 admin and some tens of containers on one Docker host.

## Deploy

1. Copy `compose.yaml` and `.env.example` to a folder on the Docker host.
2. Copy `.env.example` to `.env`. Set the values. Keep the secrets only in `.env`.
3. Start WT:

   ```sh
   docker compose up -d
   ```

`compose.yaml` needs the external Docker network `traefik_internal` from your Traefik stack. If you do not have it, make it: `docker network create --internal traefik_internal`.

WT reads Docker through a read-only socket proxy on the internal network `wt_docker`. WT gets to the internet (GitHub, ntfy, LLM server) through `wt_egress`. The socket proxy has no internet access. No port is published. Both containers have a read-only root filesystem, no Linux capabilities and `no-new-privileges`. WT runs as a non-root user. The data is in the `wt-data` volume.

## First setup

1. Get the setup token from the WT log:

   ```sh
   docker logs wt
   ```

2. Open WT in the browser. Enter the token.
3. Add the TOTP key to your authenticator app. Set a password (12 characters or more). Enter a TOTP code.

The token works one time only. WT then asks for the password and a TOTP code at each login.

## Traefik

WT must have HTTPS, because the session cookie is `Secure`. Let Traefik do TLS. Traefik gets to WT at `http://wt:8000` on the `traefik_internal` network. Add this route to the Traefik dynamic config (file provider) and set your host name:

```yaml
http:
  routers:
    wt:
      rule: Host(`wt.example.com`)
      entryPoints: [websecure]
      tls: {}
      service: wt
  services:
    wt:
      loadBalancer:
        servers:
          - url: http://wt:8000
```

WT does not read the `X-Forwarded-*` headers, so the WT log shows the IP of Traefik, not the IP of the client.

## Reset the admin

If you lose the password or the authenticator app:

```sh
docker exec wt wt reset-admin
docker restart wt
docker logs wt
```

The reset deletes the password, the TOTP key and all sessions. After the restart, the log has a new setup token. Do the first setup again. The settings and the container data stay.

## Backup

1. Stop WT: `docker compose stop wt`
2. Copy the `wt-data` volume:

   ```sh
   docker run --rm -v wt-data:/data:ro -v "$PWD":/backup alpine tar czf /backup/wt-data.tgz -C /data .
   ```

3. Start WT: `docker compose start wt`

Do not copy `wt.db` while WT runs. The copy can lose data that is still in the WAL file.

To move only the settings and the release sources, use Export and Import on the Settings page. The export has no secrets.

## Env vars

| Name | Default | Use |
| --- | --- | --- |
| `DOCKER_HOST` | none | Docker API URL. `compose.yaml` sets it to the socket proxy. |
| `WT_DATA_DIR` | `/data` | Folder for the SQLite DB. |
| `WT_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |
| `WT_GITHUB_API_URL` | `https://api.github.com` | GitHub API URL. Change it only for tests. |
| `WT_GITHUB_TOKEN` | none | Secret. GitHub token for a higher API rate limit. |
| `WT_NTFY_TOKEN` | none | Secret. ntfy access token. |
| `WT_LLM_API_KEY` | none | Secret. API key of the LLM server. |

`.env.example` does not have `DOCKER_HOST`, `WT_DATA_DIR` and `WT_GITHUB_API_URL`. `compose.yaml` sets `DOCKER_HOST`, and the defaults of the other two are correct for a deploy.

Each secret can also come from a file: set `WT_<NAME>_FILE` (for example, `WT_NTFY_TOKEN_FILE=/run/secrets/ntfy_token`). Do not set both.

All other settings (check interval, restart loop rule, ntfy, LLM, WT URL) are on the Settings page.

To test ntfy, click **Send test notification** on the Settings page. WT sends a test message with the values in the form and `WT_NTFY_TOKEN`. It does not save the values. Thus you can test before and after you save.

Container labels:

 - `wt.enable=false`: WT does not show or watch this container.
 - `org.opencontainers.image.source`: the GitHub URL of the release source. You can change it on the container page.
