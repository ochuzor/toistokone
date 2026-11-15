from __future__ import annotations

import math
import random
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .sentences import blank_form, matches_form


@dataclass(frozen=True)
class Candidate:
    card_type: str
    base_word: str
    target_form: str
    score: int
    last_practiced_at: str | None


def select_candidates(candidates: list[Candidate], batch_size: int, rng: random.Random) -> list[Candidate]:
    """Apply the PRD's non-backfilling 70/30/up-to-five-new selection rule."""
    def take(items: list[Candidate], limit: int) -> list[Candidate]:
        shuffled = list(items)
        rng.shuffle(shuffled)
        shuffled.sort(key=lambda card: (card.last_practiced_at is not None, card.last_practiced_at or ""))
        return shuffled[:limit]

    quota_12 = math.floor(0.7 * batch_size)
    quota_3 = batch_size - quota_12
    selected = take([card for card in candidates if card.score in (1, 2)], quota_12)
    selected.extend(take([card for card in candidates if card.score == 3], quota_3))
    if len(selected) < batch_size:
        selected.extend(take([card for card in candidates if card.score == 0], min(5, batch_size - len(selected))))
    rng.shuffle(selected)
    return selected


def _load_content(content_path: Path, progress_path: Path) -> tuple[dict[str, list[str]], dict[str, list[str]], list[tuple[str, list[str]]], list[Candidate]]:
    with sqlite3.connect(content_path) as connection:
        connection.execute("ATTACH DATABASE ? AS progress", (str(progress_path),))
        vocabulary: dict[str, list[str]] = {}
        for word, meaning in connection.execute(
            """SELECT vocabulary.finnish, vocabulary_meanings.meaning
               FROM vocabulary JOIN vocabulary_meanings ON vocabulary.id = vocabulary_meanings.vocabulary_id
               ORDER BY vocabulary.id, vocabulary_meanings.ordinal"""
        ):
            vocabulary.setdefault(word, []).append(meaning)
        forms: dict[str, list[str]] = {}
        for word, form in connection.execute(
            """SELECT vocabulary.finnish, word_forms.form
               FROM vocabulary JOIN word_forms ON vocabulary.id = word_forms.vocabulary_id
               ORDER BY vocabulary.id, word_forms.id"""
        ):
            forms.setdefault(word, []).append(form)
        translations: dict[int, list[str]] = {}
        for sentence_id, english in connection.execute(
            "SELECT sentence_id, english FROM sentence_translations ORDER BY sentence_id, ordinal"
        ):
            translations.setdefault(sentence_id, []).append(english)
        sentences = [(finnish, translations.get(sentence_id, [])) for sentence_id, finnish in connection.execute("SELECT id, finnish FROM sentences ORDER BY id")]

        candidates: list[Candidate] = []
        for word, score, last_practiced_at in connection.execute(
            """SELECT vocabulary.finnish, COALESCE(progress.card_progress.score, 0), progress.card_progress.last_practiced_at
               FROM vocabulary LEFT JOIN progress.card_progress
                 ON progress.card_progress.card_type = 'vocabulary'
                 AND progress.card_progress.base_word = vocabulary.finnish
                 AND progress.card_progress.target_form = ''"""
        ):
            candidates.append(Candidate("vocabulary", word, "", score, last_practiced_at))
        for base_word, form, score, last_practiced_at, parent_score in connection.execute(
            """SELECT vocabulary.finnish, word_forms.form, COALESCE(form_progress.score, 0),
                      form_progress.last_practiced_at, COALESCE(parent_progress.score, 0)
               FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id
               LEFT JOIN progress.card_progress AS form_progress
                 ON form_progress.card_type = 'word_form'
                 AND form_progress.base_word = vocabulary.finnish
                 AND form_progress.target_form = word_forms.form
               LEFT JOIN progress.card_progress AS parent_progress
                 ON parent_progress.card_type = 'vocabulary'
                 AND parent_progress.base_word = vocabulary.finnish
                 AND parent_progress.target_form = ''"""
        ):
            if parent_score == 3 and any(matches_form(sentence, form) for sentence, _ in sentences):
                candidates.append(Candidate("word_form", base_word, form, score, last_practiced_at))
    return vocabulary, forms, sentences, candidates


def _options(texts: list[str], correct_text: str, rng: random.Random) -> tuple[list[dict[str, str]], str]:
    options = [{"id": str(uuid.uuid4()), "text": text} for text in texts]
    correct_id = next(option["id"] for option in options if option["text"] == correct_text)
    rng.shuffle(options)
    return options, correct_id


def build_batch(content_path: Path, progress_path: Path, batch_size: int, rng: random.Random | None = None) -> list[dict[str, object]]:
    rng = rng or random.Random()
    vocabulary, forms, sentences, candidates = _load_content(content_path, progress_path)
    questions: list[dict[str, object]] = []
    for card in select_candidates(candidates, batch_size, rng):
        if card.card_type == "vocabulary":
            correct_text = " / ".join(vocabulary[card.base_word])
            distractors = list({" / ".join(meanings) for word, meanings in vocabulary.items() if word != card.base_word})
            rng.shuffle(distractors)
            options, correct_id = _options([correct_text, *distractors[:3]], correct_text, rng)
            prompt = card.base_word
            english_translations: list[str] = []
        else:
            matching_sentences = [(sentence, translations) for sentence, translations in sentences if matches_form(sentence, card.target_form)]
            sentence, english_translations = rng.choice(matching_sentences)
            prompt = blank_form(sentence, card.target_form)
            distinct_forms = list(dict.fromkeys(forms[card.base_word]))
            distractors = [form for form in distinct_forms if form != card.target_form]
            rng.shuffle(distractors)
            options, correct_id = _options([card.target_form, *distractors[:3]], card.target_form, rng)
        questions.append(
            {
                "question_id": str(uuid.uuid4()),
                "card": {"type": card.card_type, "base_word": card.base_word, "target_form": card.target_form},
                "score": card.score,
                "prompt": prompt,
                "english_translations": english_translations,
                "options": options,
                "correct_option_id": correct_id,
            }
        )
    return questions
