from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


CardType = Literal["vocabulary", "word_form"]


class CardReference(BaseModel):
    type: CardType
    base_word: str
    target_form: str = ""


class AnswerRequest(BaseModel):
    attempt_id: str
    card: CardReference
    selected_option_id: str
    correct_option_id: str


class AnswerResult(BaseModel):
    correct: bool
    score_before: int
    score_after: int
    mastered: bool


class ResetRequest(BaseModel):
    card: CardReference


class ResetResult(BaseModel):
    score: int


class CardStats(BaseModel):
    total: int
    mastered: int


class OverallStats(CardStats):
    mastery_percent: float


class DailyActivity(BaseModel):
    date: str
    attempts: int
    correct: int
    accuracy_percent: float
    unique_cards: int
    score_increases: int
    newly_mastered: int


class PracticeActivity(BaseModel):
    today: DailyActivity
    days: list[DailyActivity]
    streak_days: int


class StatsResponse(BaseModel):
    vocabulary: CardStats
    word_forms: CardStats
    overall: OverallStats
    activity: PracticeActivity


class RecommendationExample(BaseModel):
    finnish: str
    english_translations: list[str]


class Recommendation(BaseModel):
    word: str
    frequency_rank: int
    frequency_count: int
    related_vocabulary_count: int
    observed_forms: list[str]
    chain_words: list[str]
    examples: list[RecommendationExample]


class RecommendationsResponse(BaseModel):
    recommendations: list[Recommendation]


class VocabularyEntry(BaseModel):
    finnish: str
    meanings: list[str]
    score: int
    last_practiced_at: str | None
    focus_requested_at: str | None


class VocabularyResponse(BaseModel):
    vocabulary: list[VocabularyEntry]


class FocusWordRequest(BaseModel):
    base_word: str


class FocusWordResponse(BaseModel):
    base_word: str
    requested_at: str


class LearningSetCardStats(BaseModel):
    total: int
    mastered: int


class LearningSet(BaseModel):
    key: str
    title: str
    words: LearningSetCardStats
    word_forms: LearningSetCardStats
    active: bool


class LearningSetsResponse(BaseModel):
    learning_sets: list[LearningSet]


class LearningSetWord(BaseModel):
    finnish: str
    meanings: list[str]
    score: int
    word_forms: LearningSetCardStats


class LearningSetDetail(BaseModel):
    key: str
    title: str
    active: bool
    words: list[LearningSetWord]


class LearningPathProgress(BaseModel):
    total: int
    qualified: int
    percent: float


class LearningPathStep(BaseModel):
    ordinal: int
    key: str
    title: str
    state: Literal["completed", "available", "locked"]
    vocabulary: LearningPathProgress
    word_forms: LearningPathProgress


class LearningPath(BaseModel):
    key: str
    title: str
    sets: LearningSetCardStats
    completed: bool


class LearningPathsResponse(BaseModel):
    learning_paths: list[LearningPath]


class LearningPathDetail(BaseModel):
    key: str
    title: str
    steps: list[LearningPathStep]
    completed: bool


class ActiveLearningSetRequest(BaseModel):
    set_key: str | None = None


class ActiveLearningSetResponse(BaseModel):
    set_key: str | None = None


class ContentVersionResponse(BaseModel):
    revision: str


class QuizOption(BaseModel):
    id: str
    text: str


class QuizQuestion(BaseModel):
    question_id: str
    card: CardReference
    score: int
    prompt: str
    hint: str | None = None
    english_translations: list[str]
    options: list[QuizOption]
    correct_option_id: str


class QuizBatchResponse(BaseModel):
    questions: list[QuizQuestion]


class PracticeSentence(BaseModel):
    finnish: str
    english_translations: list[str]


class SentenceBreakResponse(BaseModel):
    sentences: list[PracticeSentence]


ContentHealthCategory = Literal["missing_profiles", "base_without_sentences", "under_supported_forms", "untracked_sentences"]


class ContentHealthSummary(BaseModel):
    missing_profiles: int
    base_without_sentences: int
    under_supported_forms: int
    untracked_sentences: int


class ContentHealthFinding(BaseModel):
    word: str | None = None
    base_word: str | None = None
    form: str | None = None
    prompt_label: str | None = None
    sentence_count: int | None = None
    finnish: str | None = None
    english_translations: list[str] | None = None
    priority_reason: str | None = None


class ContentHealthResponse(BaseModel):
    summary: ContentHealthSummary
    category: ContentHealthCategory
    offset: int
    total: int
    findings: list[ContentHealthFinding]
