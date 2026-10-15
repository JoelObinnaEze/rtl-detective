from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Annotated, Callable, Literal, Protocol

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator


TERMINAL_STATES = {"completed", "unresolved", "invalid_input", "cancelled", "infrastructure_error"}


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    example_id: str | None = Field(default=None, alias="exampleId", max_length=64)
    source: str | None = Field(default=None, max_length=256 * 1024)
    contract_id: Literal["fifo", "arbiter"] = Field(default="fifo", alias="contractId")
    data_width: int = Field(default=8, alias="dataWidth", ge=1, le=64)
    depth: int = Field(default=4, ge=1, le=1024)
    requesters: int = Field(default=4, ge=2, le=32)

    @model_validator(mode="after")
    def exactly_one_source(self) -> "CreateRunRequest":
        if (self.example_id is None) == (self.source is None):
            raise ValueError("provide exactly one of exampleId or source")
        return self


class Manager(Protocol):
    def submit(self, request: CreateRunRequest, idempotency_key: str | None) -> str: ...
    def get_run(self, run_id: str) -> dict[str, object]: ...
    def cancel(self, run_id: str) -> None: ...
    def examples(self) -> list[dict[str, object]]: ...
    def list_artifacts(self, run_id: str) -> list[dict[str, object]]: ...
    def artifact_path(self, run_id: str, name: str) -> Path: ...


def _error(status: int, code: str, message: str, details: object | None = None) -> JSONResponse:
    body: dict[str, object] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details  # type: ignore[index]
    return JSONResponse(status_code=status, content=body)


def create_app(
    manager: Manager,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
) -> FastAPI:
    app = FastAPI(title="RTL Detective", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError):
        return _error(422, "VALIDATION_ERROR", "Request validation failed", jsonable_encoder(error.errors()))

    @app.post("/api/runs", status_code=202)
    def create_run(
        body: CreateRunRequest,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
    ) -> dict[str, str]:
        try:
            run_id = manager.submit(body, idempotency_key)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error
        return {"id": run_id, "status": "queued"}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        try:
            return manager.get_run(run_id)
        except KeyError as error:
            raise HTTPException(404, "run not found") from error

    @app.get("/api/runs/{run_id}/events", response_class=EventSourceResponse)
    async def stream_events(run_id: str):
        seen = 0
        while True:
            try:
                record = manager.get_run(run_id)
            except KeyError:
                yield ServerSentEvent(data={"error": "run not found"}, event="error")
                return
            for event in record.get("events", []):
                sequence = int(event["sequence"])
                if sequence > seen:
                    seen = sequence
                    yield ServerSentEvent(data=event, event="run_event", id=str(sequence))
            if record["status"] in TERMINAL_STATES:
                yield ServerSentEvent(data={"status": record["status"]}, event="done")
                return
            await asyncio.sleep(0.25)

    @app.post("/api/runs/{run_id}/cancel", status_code=202)
    def cancel_run(run_id: str) -> dict[str, str]:
        try:
            manager.cancel(run_id)
        except KeyError as error:
            raise HTTPException(404, "run not found") from error
        return {"id": run_id, "status": "cancellation_requested"}

    @app.get("/api/runs/{run_id}/artifacts")
    def list_artifacts(run_id: str) -> list[dict[str, object]]:
        try:
            return manager.list_artifacts(run_id)
        except KeyError as error:
            raise HTTPException(404, "run not found") from error

    @app.get("/api/runs/{run_id}/artifacts/{name}")
    def download_artifact(run_id: str, name: str) -> FileResponse:
        try:
            path = manager.artifact_path(run_id, name)
        except KeyError as error:
            raise HTTPException(404, "artifact not found") from error
        return FileResponse(path, filename=path.name)

    @app.get("/api/examples")
    def examples() -> list[dict[str, object]]:
        return manager.examples()

    frontend = Path(__file__).parents[1] / "frontend"
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app

