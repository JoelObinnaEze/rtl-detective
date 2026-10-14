from backend.cli import main


def test_model_discovery_requires_backend_credential(monkeypatch, capsys) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    exit_code = main(["models"])

    assert exit_code == 2
    assert "NEBIUS_API_KEY" in capsys.readouterr().err

