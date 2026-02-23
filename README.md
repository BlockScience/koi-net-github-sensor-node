# koi-net-github-sensor-node

## Overview
GitHub sensor node that polls configured repositories and emits KOI bundles.

## Prerequisites
- Python 3.10+
- `uv`

## Environment
Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Required:
- `PRIV_KEY_PASSWORD`

Optional runtime targeting/overrides:
- `GITHUB_API_TOKEN`
- `GITHUB_REPOSITORIES` (comma-separated: `owner/repo,owner2/repo2`)
- `GITHUB_POLL_INTERVAL_SECONDS`
- `GITHUB_STATE_PATH`

Precedence:
- `.env` overrides are applied first when non-empty.
- If env override is empty, node falls back to `config.yaml` values.

## Quick Start
```bash
uv sync --refresh --reinstall
set -a; source .env; set +a
uv run python -m koi_net_github_sensor_node
```

Expected startup signal: node runs on `127.0.0.1:8007` and logs repository polling activity.

## First Contact / Networking
- Default first contact is coordinator: `http://127.0.0.1:8080/koi-net`.
- Default node port: `8007`.

## Config Generation
- `config.yaml` is auto-generated on first run.
- `config.yaml.example` contains all defaults, including env mappings.

## Troubleshooting
- No repos polled: set `GITHUB_REPOSITORIES` or configure `github.repositories` in `config.yaml`.
- API rate limits: set `GITHUB_API_TOKEN`.
- Missing `PRIV_KEY_PASSWORD`: export env before startup.
