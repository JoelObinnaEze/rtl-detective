# Judge Deployment Runbook

The judge build uses the included `Dockerfile` and `render.yaml` on Render's free web-service tier. It matches the application's one-worker SQLite architecture and keeps hosting separate from the Nebius inference budget. The manual Linux VM path below remains the rollback option.

## Render judge deployment

1. Publish the repository and create a Render Blueprint from its public GitHub URL.
2. Keep the Blueprint's `free` plan and enter `NEBIUS_API_KEY` only in Render's secret prompt.
3. Wait for `/api/health` to pass, then open the assigned `onrender.com` URL.
4. Run `case-005` first for a no-inference smoke test. Run `case-001` only when recording or validating the live model path.

The container includes Verilator 5.050, binds FastAPI to Render's `PORT`, and allows one queued/active run. Render's free filesystem is ephemeral and can cold-start after 15 idle minutes, so proof bundles should be downloaded before a restart. Because the hosted container has no Docker socket, the trusted bundled examples run locally while pasted RTL stays disabled; that preserves the isolation boundary instead of executing public uploads in the web-service process.

## Manual Linux VM fallback

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
MAX_PENDING_RUNS=4
ARTIFACTS_DIRECTORY=/srv/rtl-detective/artifacts
```

Start the app on loopback and terminate TLS at the reverse proxy:

```bash
.venv/bin/python -m backend.cli serve --host 127.0.0.1 --port 8000
```

Proxy the public origin to `127.0.0.1:8000`, preserving streaming responses. Apply an edge request and body-size limit to `POST /api/runs`; the app intentionally has no multi-tenant account system. Its in-process queue rejects work beyond `MAX_PENDING_RUNS`, but that is not a distributed rate limiter. Keep the process at one instance because run state and SQLite artifacts are local.

For Nginx, define `limit_req_zone $binary_remote_addr zone=rtl_runs:10m rate=2r/m;` in the `http` block, then apply `limit_req zone=rtl_runs burst=1 nodelay;` and `client_max_body_size 300k;` in the exact `location = /api/runs` block. Disable proxy buffering for `/api/runs/` so server-sent events reach the browser immediately.

## Acceptance checks

1. `GET https://<PUBLIC_HOST>/api/health` returns `status: ok`, `repairReady: true`, `configured: true`, `maxPendingRuns: 4`, and `nvidia/nemotron-3-super-120b-a12b`. It must never return the API key.
2. Run `case-005`; it should pass the baseline without an AI call.
3. Run `case-001` once; it should show the Nebius/NVIDIA provider proof and either a verified candidate or honest unresolved evidence.
4. Download `report.md`, `report.json`, and `artifact-bundle.zip` from the completed run.
5. Check the mobile layout at 320 px and desktop layout at 1440 px, browser console, SSE progress, and HTTPS certificate.
6. Confirm the Docker worker has no network, a read-only root filesystem, dropped capabilities, a non-root UID, and the configured resource limits.

## Cost and abuse controls

- The default repair uses at most one investigation request and one patch request, with no provider retries.
- Correct examples make no model request.
- The app admits at most four active or queued runs by default; rate-limit new runs at the reverse proxy and monitor Token Factory usage during judging.
- Keep only the required judge window online. The official rules require free access through December 15, 2026; do not disable the demo earlier.
- Rotate the API key immediately if it appears in logs, a recording, or repository history.

## Operations and rollback

- Monitor `/api/health`, queue-full responses, process restarts, disk use under `artifacts/`, Docker failures, and Token Factory spend. Restart recovery marks any abandoned nonterminal run as interrupted and writes a failure proof bundle.
- Back up any proof bundle you plan to cite before pruning old run directories.
- Deploy by immutable Git commit. Roll back by checking out the previous verified commit and restarting the service; do not reuse partially written run directories.
