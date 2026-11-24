from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping
import sqlite3
from pathlib import Path

from .sentences import matches_form, tokens


@dataclass(frozen=True)
class FormHealthFinding:
    base_word: str
    form: str
    prompt_label: str
    sentence_count: int
    priority_reason: str


@dataclass(frozen=True)
class WordHealthFinding:
    word: str
    priority_reason: str


@dataclass(frozen=True)
class SentenceHealthFinding:
    finnish: str
    english_translations: list[str]
    priority_reason: str


@dataclass(frozen=True)
class ContentHealth:
    missing_profiles: list[WordHealthFinding]
    base_without_sentences: list[WordHealthFinding]
    under_supported_forms: list[FormHealthFinding]
    untracked_sentences: list[SentenceHealthFinding]

    def summary(self) -> dict[str, int]:
        return {
            "missing_profiles": len(self.missing_profiles),
            "base_without_sentences": len(self.base_without_sentences),
            "under_supported_forms": len(self.under_supported_forms),
            "untracked_sentences": len(self.untracked_sentences),
        }


@dataclass(frozen=True)
class PriorityContext:
    focus_words: set[str]
    last_practised: Mapping[str, str]
    frequency_ranks: Mapping[str, int]


def _priority_context(progress_path: Path | None, frequency_ranks: Mapping[str, int] | None) -> PriorityContext:
    focus_words: set[str] = set()
    last_practised: dict[str, str] = {}
    if progress_path and progress_path.exists():
        try:
            with sqlite3.connect(f"file:{progress_path}?mode=ro", uri=True) as connection:
                focus_words = {word for word, in connection.execute("SELECT base_word FROM focus_vocabulary")}
                last_practised = {
                    word: practiced_at
                    for word, practiced_at in connection.execute(
                        """SELECT base_word, MAX(last_practiced_at)
                           FROM card_progress
                           WHERE last_practiced_at IS NOT NULL
                           GROUP BY base_word"""
                    )
                }
        except sqlite3.Error:
            pass
    return PriorityContext(focus_words, last_practised, frequency_ranks or {})


def _frequency_rank(context: PriorityContext, base_word: str, surface: str | None = None) -> int | None:
    if surface:
        rank = context.frequency_ranks.get(surface.casefold())
        if rank is not None:
            return rank
    return context.frequency_ranks.get(base_word.casefold())


def _coverage_priority(context: PriorityContext, base_word: str, surface: str | None = None) -> tuple[tuple[object, ...], str]:
    if base_word in context.focus_words:
        return ((0, 0, 0, base_word.casefold(), (surface or "").casefold()), "Focus word")
    practiced_at = context.last_practised.get(base_word)
    if practiced_at:
        try:
            recency = -datetime.fromisoformat(practiced_at).timestamp()
        except ValueError:
            recency = 0.0
        return ((1, recency, 0, base_word.casefold(), (surface or "").casefold()), "Practised recently")
    rank = _frequency_rank(context, base_word, surface)
    if rank is not None:
        return ((2, 0, rank, base_word.casefold(), (surface or "").casefold()), f"Frequency rank #{rank}")
    return ((3, 0, 0, base_word.casefold(), (surface or "").casefold()), "No frequency rank")


def _sentence_priority(context: PriorityContext, sentence: str) -> tuple[tuple[object, ...], str]:
    sentence_tokens = tokens(sentence)
    token_count = len(sentence_tokens)
    ranks = [context.frequency_ranks.get(token) for token in sentence_tokens]
    missing_count = sum(rank is None for rank in ranks)
    least_common_rank = max((rank for rank in ranks if rank is not None), default=float("inf"))
    key = (missing_count, least_common_rank, token_count, sentence.casefold())
    word_label = "word" if token_count == 1 else "words"
    if missing_count:
        return key, f"{token_count} {word_label} · {missing_count} outside frequency list"
    return key, f"{token_count} {word_label} · least-common word rank #{least_common_rank}"


def _single_token(value: str) -> str | None:
    value_tokens = tokens(value)
    if len(value_tokens) != 1:
        return None
    token = next(iter(value_tokens))
    return token if token == value.casefold() else None


def analyze_content_health(
    vocabulary: Iterable[str],
    forms: Iterable[tuple[str, str, str]],
    sentences: Mapping[str, list[str]],
    *,
    progress_path: Path | None = None,
    frequency_ranks: Mapping[str, int] | None = None,
) -> ContentHealth:
    vocabulary_words = list(vocabulary)
    form_rows = list(forms)
    priority_context = _priority_context(progress_path, frequency_ranks)
    sentence_tokens: dict[str, set[str]] = {sentence: tokens(sentence) for sentence in sentences}
    by_token: dict[str, set[str]] = defaultdict(set)
    for sentence, sentence_token_set in sentence_tokens.items():
        for token in sentence_token_set:
            by_token[token].add(sentence)

    tracked_surfaces = [*vocabulary_words, *(form for _, form, _ in form_rows)]

    def matching_sentences(surface: str) -> set[str]:
        token = _single_token(surface)
        if token is not None:
            return by_token.get(token, set())
        return {sentence for sentence in sentences if matches_form(sentence, surface)}

    supported_by_surface = {surface: matching_sentences(surface) for surface in set(tracked_surfaces)}
    form_bases = {base_word for base_word, _, _ in form_rows}
    missing_profiles = sorted(
        (WordHealthFinding(word, _coverage_priority(priority_context, word)[1]) for word in vocabulary_words if word not in form_bases),
        key=lambda item: _coverage_priority(priority_context, item.word)[0],
    )
    base_without_sentences = sorted(
        (WordHealthFinding(word, _coverage_priority(priority_context, word)[1]) for word in vocabulary_words if not supported_by_surface[word]),
        key=lambda item: _coverage_priority(priority_context, item.word)[0],
    )
    under_supported_forms = sorted(
        (
            FormHealthFinding(base_word, form, prompt_label, len(supported_by_surface[form]), _coverage_priority(priority_context, base_word, form)[1])
            for base_word, form, prompt_label in form_rows
            if len(supported_by_surface[form]) < 2
        ),
        key=lambda item: _coverage_priority(priority_context, item.base_word, item.form)[0],
    )
    tracked_sentences = set().union(*supported_by_surface.values()) if supported_by_surface else set()
    untracked_sentences = [
        SentenceHealthFinding(sentence, list(translations), _sentence_priority(priority_context, sentence)[1])
        for sentence, translations in sentences.items()
        if sentence not in tracked_sentences
    ]
    untracked_sentences.sort(key=lambda item: _sentence_priority(priority_context, item.finnish)[0])
    return ContentHealth(missing_profiles, base_without_sentences, under_supported_forms, untracked_sentences)


def get_content_health(content_path: Path, progress_path: Path | None = None) -> ContentHealth:
    with sqlite3.connect(content_path) as connection:
        vocabulary = [word for word, in connection.execute("SELECT finnish FROM vocabulary ORDER BY id")]
        forms = list(connection.execute(
            """SELECT vocabulary.finnish, word_forms.form, word_forms.prompt_label
               FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id
               ORDER BY word_forms.id"""
        ))
        sentences: dict[str, list[str]] = {}
        for finnish, english in connection.execute(
            """SELECT sentences.finnish, sentence_translations.english
               FROM sentences JOIN sentence_translations ON sentence_translations.sentence_id = sentences.id
               ORDER BY sentences.id, sentence_translations.ordinal"""
        ):
            sentences.setdefault(finnish, []).append(english)
        frequency_ranks = {token: rank for token, rank in connection.execute(
            "SELECT token_casefold, frequency_rank FROM frequency_words"
        )}
    return analyze_content_health(vocabulary, forms, sentences, progress_path=progress_path, frequency_ranks=frequency_ranks)
