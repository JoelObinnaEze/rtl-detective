from pathlib import Path

from backend.verification.runner import container_security_args


def test_container_worker_is_networkless_read_only_and_resource_bounded(tmp_path: Path) -> None:
    args = container_security_args(tmp_path, "worker-1")
    command = " ".join(args)

    assert "--network none" in command
    assert "--read-only" in args
    assert "--cap-drop ALL" in command
    assert "no-new-privileges:true" in command
    assert "--memory 512m" in command
    assert "--cpus 1" in command
    assert "--pids-limit 128" in command
    assert "--user" in args
    assert all("NEBIUS" not in value for value in args)
    assert str(tmp_path.resolve()) in command

