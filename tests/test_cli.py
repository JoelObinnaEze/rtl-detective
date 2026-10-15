from backend.cli import _parser, main


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

