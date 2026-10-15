from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


class IdempotencyConflict(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    verdict TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    provider_mode TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    UNIQUE(run_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    key TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE
                );
                """
            )

    def create_run(
        self,
        parameters: dict[str, int | str],
        provider_mode: str,
        source_kind: str,
        idempotency_key: str | None = None,
        request_hash: str | None = None,
    ) -> str:
        if idempotency_key and not request_hash:
            raise ValueError("request_hash is required with an idempotency key")
        run_id = uuid4().hex
        timestamp = _now()
        parameters_json = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                existing = connection.execute(
                    "SELECT request_hash, run_id FROM idempotency WHERE key = ?", (idempotency_key,)
                ).fetchone()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise IdempotencyConflict("idempotency key was reused with a different payload")
                    return str(existing["run_id"])
            connection.execute(
                """INSERT INTO runs
                   (id, status, created_at, updated_at, parameters_json, provider_mode, source_kind)
                   VALUES (?, 'queued', ?, ?, ?, ?, ?)""",
                (run_id, timestamp, timestamp, parameters_json, provider_mode, source_kind),
            )
            if idempotency_key:
                connection.execute(
                    "INSERT INTO idempotency (key, request_hash, run_id) VALUES (?, ?, ?)",
                    (idempotency_key, request_hash, run_id),
                )
        return run_id

    def append_event(self, run_id: str, state: str, message: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO events (run_id, sequence, created_at, state, message) VALUES (?, ?, ?, ?, ?)",
                (run_id, sequence, _now(), state, message),
            )

    def update_run(self, run_id: str, status: str, verdict: str | None = None) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE runs SET status = ?, verdict = ?, updated_at = ? WHERE id = ?",
                (status, verdict, _now(), run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def request_cancel(self, run_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE runs SET cancel_requested = 1, updated_at = ? WHERE id = ?", (_now(), run_id)
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def is_cancelled(self, run_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT cancel_requested FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        return bool(row["cancel_requested"])

    def get_run(self, run_id: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            events = connection.execute(
                "SELECT sequence, created_at, state, message FROM events WHERE run_id = ? ORDER BY sequence",
                (run_id,),
            ).fetchall()
        if not row:
            raise KeyError(run_id)
        return {
            "id": row["id"],
            "status": row["status"],
            "verdict": row["verdict"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "parameters": json.loads(row["parameters_json"]),
            "provider_mode": row["provider_mode"],
            "source_kind": row["source_kind"],
            "cancel_requested": bool(row["cancel_requested"]),
            "events": [dict(event) for event in events],
        }

    def list_runs(self, limit: int = 50) -> list[dict[str, object]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.get_run(str(row["id"])) for row in rows]

