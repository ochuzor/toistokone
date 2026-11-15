from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .config import Settings, load_settings
from .db import card_exists, get_stats, initialize_progress_database, record_answer, reset_card
from .models import AnswerRequest, AnswerResult, ResetRequest, ResetResult, StatsResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = load_settings()
    initialize_progress_database(app.state.settings.progress_db_path)
    yield


app = FastAPI(title="ToistoKone", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_settings() -> Settings:
    """Expose loaded settings for future route modules."""
    return app.state.settings


def _require_card(card: ResetRequest | AnswerRequest) -> None:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    if not card_exists(settings.content_db_path, card.card):
        raise HTTPException(status_code=404, detail="Card does not exist in current content.")


@app.post("/api/answers", response_model=AnswerResult)
def answer(request: AnswerRequest) -> AnswerResult:
    _require_card(request)
    result = record_answer(
        get_settings().progress_db_path,
        request.card,
        request.attempt_id,
        request.selected_option_id == request.correct_option_id,
    )
    return AnswerResult(**result, mastered=result["score_after"] == 3)


@app.post("/api/cards/reset", response_model=ResetResult)
def reset(request: ResetRequest) -> ResetResult:
    _require_card(request)
    return ResetResult(score=reset_card(get_settings().progress_db_path, request.card))


@app.get("/api/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    return StatsResponse(**get_stats(settings.content_db_path, settings.progress_db_path))
