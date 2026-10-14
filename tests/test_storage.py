from pathlib import Path

import pytest

from backend.storage import IdempotencyConflict, RunStore


def test_run_events_and_terminal_result_are_persistent(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    run_id = store.create_run(
        parameters={"data_width": 8, "depth": 3},
        provider_mode="live",
        source_kind="example",
        idempotency_key="intent-1",
        request_hash="hash-1",
    )
    store.append_event(run_id, "baseline", "Running locked tests")
    store.update_run(run_id, status="completed", verdict="no_failure_found_in_tested_cases")

    record = store.get_run(run_id)

    assert record["status"] == "completed"
    assert record["parameters"] == {"data_width": 8, "depth": 3}
    assert record["events"][0]["sequence"] == 1
    assert record["events"][0]["state"] == "baseline"


def test_idempotency_key_replays_same_intent_and_rejects_different_payload(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    first = store.create_run(
        {"data_width": 8, "depth": 3}, "live", "example", "intent-1", "hash-1"
    )
    replay = store.create_run(
        {"data_width": 8, "depth": 3}, "live", "example", "intent-1", "hash-1"
    )

    assert replay == first
    with pytest.raises(IdempotencyConflict):
        store.create_run({"data_width": 16, "depth": 7}, "live", "example", "intent-1", "hash-2")


def test_cancellation_flag_is_scoped_to_run(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    first = store.create_run({"data_width": 8, "depth": 3}, "live", "example")
    second = store.create_run({"data_width": 8, "depth": 3}, "live", "example")

    store.request_cancel(first)

    assert store.is_cancelled(first) is True
    assert store.is_cancelled(second) is False

