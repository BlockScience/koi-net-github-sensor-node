# koi-net-github-sensor-node

GitHub sensor node implementation for KOI-net.

## Prerequisites

- Python 3.10+
- `uv` installed

## Environment Setup

1. Create environment file:
   `cp .env.example .env`
2. Set `PRIV_KEY_PASSWORD` in `.env`
3. Optional: set `GITHUB_API_TOKEN` in `.env` for authenticated GitHub API access

`PRIV_KEY_PASSWORD` is required for loading or generating the node private key.

## Configure Node

Edit `config.yaml`:

- `github.api_token` (optional; if empty, uses `env.GITHUB_API_TOKEN`)
- `github.repositories`
- `github.poll_interval_seconds`
- `server.host` / `server.port`

## Install Dependencies

```bash
uv sync --refresh --reinstall
```

## Run

```bash
uv run python -m koi_net_github_sensor_node
```

## Notes

- On first run, if `private_key.pem` does not exist, it is generated automatically.
- If `private_key.pem` already exists, `PRIV_KEY_PASSWORD` must match the password used when that key was created.
