from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SentenceHealthFinding:
    finnish: str
    english_translations: list[str]


@dataclass(frozen=True)
class ContentHealth:
    missing_profiles: list[str]
    base_without_sentences: list[str]
    under_supported_forms: list[FormHealthFinding]
    untracked_sentences: list[SentenceHealthFinding]

    def summary(self) -> dict[str, int]:
        return {
            "missing_profiles": len(self.missing_profiles),
            "base_without_sentences": len(self.base_without_sentences),
            "under_supported_forms": len(self.under_supported_forms),
            "untracked_sentences": len(self.untracked_sentences),
        }


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
) -> ContentHealth:
    vocabulary_words = list(vocabulary)
    form_rows = list(forms)
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
    missing_profiles = sorted((word for word in vocabulary_words if word not in form_bases), key=str.casefold)
    base_without_sentences = sorted(
        (word for word in vocabulary_words if not supported_by_surface[word]), key=str.casefold
    )
    under_supported_forms = sorted(
        (
            FormHealthFinding(base_word, form, prompt_label, len(supported_by_surface[form]))
            for base_word, form, prompt_label in form_rows
            if len(supported_by_surface[form]) < 2
        ),
        key=lambda item: (item.base_word.casefold(), item.form.casefold()),
    )
    tracked_sentences = set().union(*supported_by_surface.values()) if supported_by_surface else set()
    untracked_sentences = [
        SentenceHealthFinding(sentence, list(translations))
        for sentence, translations in sentences.items()
        if sentence not in tracked_sentences
    ]
    untracked_sentences.sort(key=lambda item: item.finnish.casefold())
    return ContentHealth(missing_profiles, base_without_sentences, under_supported_forms, untracked_sentences)


def get_content_health(content_path: Path) -> ContentHealth:
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
    return analyze_content_health(vocabulary, forms, sentences)
