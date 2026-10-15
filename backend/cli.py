from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from backend.api import TERMINAL_STATES, CreateRunRequest
from backend.providers.nebius import DEFAULT_BASE_URL, NebiusProvider, ProviderError
from backend.service import RunManager


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtl-detective", description="Verify and diagnose canonical RTL blocks")
    subcommands = parser.add_subparsers(dest="command", required=True)

    verify = subcommands.add_parser("verify", help="run the locked verification workflow")
    source = verify.add_mutually_exclusive_group()
    source.add_argument("--example")
    source.add_argument("--source", type=Path)
    verify.add_argument("--contract", choices=("fifo", "arbiter"))
    verify.add_argument("--data-width", type=int)
    verify.add_argument("--depth", type=int)
    verify.add_argument("--requesters", type=int)
    verify.add_argument("--artifacts", type=Path, default=Path("artifacts"))

    subcommands.add_parser("models", help="list NVIDIA/Nemotron model IDs available to this account")

    serve = subcommands.add_parser("serve", help="start the local API and web interface")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def _verify(args: argparse.Namespace) -> int:
    manager = RunManager(args.artifacts)
    try:
        if args.source:
            request_data = {
                "source": args.source.read_text(encoding="utf-8"),
                "dataWidth": args.data_width if args.data_width is not None else 8,
                "depth": args.depth if args.depth is not None else 3,
                "requesters": args.requesters if args.requesters is not None else 4,
            }
        else:
            default_example = "arbiter-case-003" if args.contract == "arbiter" else "case-005"
            request_data = {"exampleId": args.example or default_example}
            for name, value in (
                ("dataWidth", args.data_width),
                ("depth", args.depth),
                ("requesters", args.requesters),
            ):
                if value is not None:
                    request_data[name] = value
        if args.contract:
            request_data["contractId"] = args.contract
        request = CreateRunRequest.model_validate(request_data)
        run_id = manager.submit(request, None)
        print(f"run {run_id}")
        seen = 0
        while True:
            record = manager.get_run(run_id)
            for event in record["events"]:
                if event["sequence"] > seen:
                    seen = event["sequence"]
                    print(f"[{event['state']}] {event['message']}")
            if record["status"] in TERMINAL_STATES:
                print(f"{record['status']}: {record['verdict']}")
                print(f"artifacts: {(args.artifacts / 'runs' / run_id).resolve()}")
                return 0 if record["status"] == "completed" else 1
            time.sleep(0.25)
    finally:
        manager.shutdown()


def _models() -> int:
    api_key = os.getenv("NEBIUS_API_KEY", "")
    if not api_key:
        print("NEBIUS_API_KEY is required for model discovery", file=sys.stderr)
        return 2
    try:
        provider = NebiusProvider(
            api_key=api_key,
            model_id="discovery-only",
            base_url=os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        )
        models = provider.discover_nvidia_models()
    except ProviderError as error:
        print(str(error), file=sys.stderr)
        return 1
    if not models:
        print("No NVIDIA/Nemotron model was returned for this account", file=sys.stderr)
        return 1
    print("\n".join(models))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "verify":
        try:
            return _verify(args)
        except (OSError, ValueError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
    if args.command == "models":
        return _models()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

