from pathlib import Path

import pytest

from backend.cli import _parser, main


class StubRunManager:
    submitted = None

    def __init__(self, _data_root: Path) -> None:
        pass

    def submit(self, request, _idempotency_key):
        type(self).submitted = request
        return "run-1"

    def get_run(self, _run_id: str) -> dict[str, object]:
        return {"status": "completed", "verdict": "no_failure_found_in_tested_cases", "events": []}

    def shutdown(self) -> None:
        pass


def test_model_discovery_requires_backend_credential(monkeypatch, capsys) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    exit_code = main(["models"])

    assert exit_code == 2
    assert "NEBIUS_API_KEY" in capsys.readouterr().err


def test_verify_command_accepts_a_contract_pack_and_its_parameters() -> None:
    args = _parser().parse_args(
        ["verify", "--source", "arbiter.sv", "--contract", "arbiter", "--requesters", "3"]
    )

    assert args.contract == "arbiter"
    assert args.requesters == 3


def test_verify_contract_selects_a_compatible_default_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.cli.RunManager", StubRunManager)

    exit_code = main(["verify", "--contract", "arbiter", "--artifacts", str(tmp_path)])

    assert exit_code == 0
    assert StubRunManager.submitted.example_id == "arbiter-case-003"
    assert StubRunManager.submitted.contract_id == "arbiter"
    assert "requesters" not in StubRunManager.submitted.model_fields_set


def test_verify_rejects_source_and_example_together() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["verify", "--source", "dut.sv", "--example", "case-005"])


def test_verify_reports_conflicting_contract_without_a_traceback(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "verify",
            "--contract",
            "arbiter",
            "--example",
            "case-005",
            "--artifacts",
            str(tmp_path),
        ]
    )

    assert exit_code == 2
    assert "contractId does not match" in capsys.readouterr().err

