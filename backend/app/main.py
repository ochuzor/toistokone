from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from .config import Settings, load_settings
from .db import card_exists, get_content_revision, get_stats, initialize_progress_database, list_focus_words, list_vocabulary, record_answer, remove_focus_word, request_focus_word, reset_card
from .content_health import get_content_health
from .models import AnswerRequest, AnswerResult, ContentHealthCategory, ContentHealthResponse, ContentVersionResponse, FocusWordRequest, FocusWordResponse, RecommendationsResponse, ResetRequest, ResetResult, SentenceBreakResponse, StatsResponse, VocabularyResponse
from .models import QuizBatchResponse
from .quiz import build_batch, build_sentence_break
from .recommendations import get_recommendations


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
        get_settings().card_score_cooldown_minutes,
    )
    return AnswerResult(**result, mastered=result["score_after"] == 3)


@app.post("/api/cards/reset", response_model=ResetResult)
def reset(request: ResetRequest) -> ResetResult:
    _require_card(request)
    return ResetResult(score=reset_card(get_settings().progress_db_path, request.card))


@app.get("/api/stats", response_model=StatsResponse)
def stats(timezone: str = Query(default="UTC", min_length=1, max_length=64)) -> StatsResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    try:
        return StatsResponse(**get_stats(settings.content_db_path, settings.progress_db_path, timezone))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/recommendations", response_model=RecommendationsResponse)
def recommendations() -> RecommendationsResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    return RecommendationsResponse(recommendations=get_recommendations(settings.content_db_path))


@app.get("/api/content-health", response_model=ContentHealthResponse)
def content_health(
    category: ContentHealthCategory = Query(default="missing_profiles"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=50),
) -> ContentHealthResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    health = get_content_health(settings.content_db_path, settings.progress_db_path)
    findings_by_category = {
        "missing_profiles": [finding.__dict__ for finding in health.missing_profiles],
        "base_without_sentences": [finding.__dict__ for finding in health.base_without_sentences],
        "under_supported_forms": [finding.__dict__ for finding in health.under_supported_forms],
        "untracked_sentences": [finding.__dict__ for finding in health.untracked_sentences],
    }
    findings = findings_by_category[category]
    return ContentHealthResponse(
        summary=health.summary(), category=category, offset=offset, total=len(findings), findings=findings[offset:offset + limit]
    )


@app.get("/api/content-version", response_model=ContentVersionResponse)
def content_version() -> ContentVersionResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    return ContentVersionResponse(revision=get_content_revision(settings.content_db_path))


@app.get("/api/vocabulary", response_model=VocabularyResponse)
def vocabulary(query: str = Query(default="", max_length=100)) -> VocabularyResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    return VocabularyResponse(vocabulary=list_vocabulary(settings.content_db_path, settings.progress_db_path, query))


@app.post("/api/focus-words", response_model=FocusWordResponse)
def add_focus_word(request: FocusWordRequest) -> FocusWordResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    try:
        return FocusWordResponse(**request_focus_word(settings.content_db_path, settings.progress_db_path, request.base_word))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/focus-words", response_model=VocabularyResponse)
def focus_words() -> VocabularyResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    return VocabularyResponse(vocabulary=list_focus_words(settings.content_db_path, settings.progress_db_path))


@app.delete("/api/focus-words/{base_word}", response_model=FocusWordResponse)
def delete_focus_word(base_word: str) -> FocusWordResponse:
    focused = remove_focus_word(get_settings().progress_db_path, base_word)
    if not focused:
        raise HTTPException(status_code=404, detail="Focus request does not exist")
    return FocusWordResponse(**focused)


@app.post("/api/quiz/batch", response_model=QuizBatchResponse)
def quiz_batch() -> QuizBatchResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    return QuizBatchResponse(
        questions=build_batch(settings.content_db_path, settings.progress_db_path, settings.quiz_batch_size)
    )


@app.post("/api/practice/sentence-break", response_model=SentenceBreakResponse)
def sentence_break() -> SentenceBreakResponse:
    settings = get_settings()
    if not settings.content_db_path.exists():
        raise HTTPException(status_code=503, detail="Content database is missing; run the import pipeline.")
    return SentenceBreakResponse(
        sentences=build_sentence_break(settings.content_db_path, settings.progress_db_path)
    )
