import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.api import create_app
from backend.service import RunManager

manager = RunManager(Path(os.getenv("ARTIFACTS_DIRECTORY", "artifacts")))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    manager.shutdown()


app = create_app(manager, lifespan)

