from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings, load_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = load_settings()
    yield


app = FastAPI(title="ToistoKone", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_settings() -> Settings:
    """Expose loaded settings for future route modules."""
    return app.state.settings
