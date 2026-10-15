# Judge Deployment Runbook

This runbook favors a single small Linux VM with Docker. It matches the application's one-worker SQLite architecture and avoids spending time on orchestration the demo does not need.

## Host requirements

- Python 3.11+
- Docker Engine with access to `verilator/verilator:v5.050`
- HTTPS reverse proxy such as Caddy or Nginx
- A non-root service account with write access only to the checkout's `artifacts/` directory

## Install

```bash
git clone <PUBLIC_REPOSITORY_URL> rtl-detective
cd rtl-detective
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.lock
docker pull verilator/verilator:v5.050
.venv/bin/python -m pytest -q
```

Configure secrets in the service manager or host secret store, never in Git:

```text
# Set NEBIUS_API_KEY separately in the host secret store.
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_MODEL_ID=nvidia/nemotron-3-super-120b-a12b
NEBIUS_MAX_RETRIES=0
NEBIUS_MAX_OUTPUT_TOKENS=1536
MAX_PATCH_ATTEMPTS=1
SIMULATION_TIMEOUT_SECONDS=30
ARTIFACTS_DIRECTORY=/srv/rtl-detective/artifacts
```

Start the app on loopback and terminate TLS at the reverse proxy:

```bash
.venv/bin/python -m backend.cli serve --host 127.0.0.1 --port 8000
```

Proxy the public origin to `127.0.0.1:8000`, preserving streaming responses. Apply an edge request limit to `POST /api/runs`; the app intentionally has no multi-tenant account system. Keep the process at one instance because run state and SQLite artifacts are local.

## Acceptance checks

1. `GET https://<PUBLIC_HOST>/api/health` returns `status: ok`, `configured: true`, and `nvidia/nemotron-3-super-120b-a12b`. It must never return the API key.
2. Run `case-005`; it should pass the baseline without an AI call.
3. Run `case-001` once; it should show the Nebius/NVIDIA provider proof and either a verified candidate or honest unresolved evidence.
4. Download `report.md`, `report.json`, and `artifact-bundle.zip` from the completed run.
5. Check the mobile layout at 320 px and desktop layout at 1440 px, browser console, SSE progress, and HTTPS certificate.
6. Confirm the Docker worker has no network, a read-only root filesystem, dropped capabilities, a non-root UID, and the configured resource limits.

## Cost and abuse controls

- The default repair uses at most one investigation request and one patch request, with no provider retries.
- Correct examples make no model request.
- Rate-limit new runs at the reverse proxy and monitor Token Factory usage during judging.
- Keep only the required judge window online. The official rules require free access through December 15, 2026; do not disable the demo earlier.
- Rotate the API key immediately if it appears in logs, a recording, or repository history.

## Operations and rollback

- Monitor `/api/health`, process restarts, disk use under `artifacts/`, Docker failures, and Token Factory spend.
- Back up any proof bundle you plan to cite before pruning old run directories.
- Deploy by immutable Git commit. Roll back by checking out the previous verified commit and restarting the service; do not reuse partially written run directories.
