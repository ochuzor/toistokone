from __future__ import annotations

import math
import random
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .sentences import blank_form, matches_form, tokens


@dataclass(frozen=True)
class Candidate:
    card_type: str
    base_word: str
    target_form: str
    score: int
    last_practiced_at: str | None
    frequency_rank: int | None = None


def select_candidates(candidates: list[Candidate], batch_size: int, rng: random.Random) -> list[Candidate]:
    """Apply the PRD's non-backfilling 70/30/up-to-five-new selection rule."""
    def take(items: list[Candidate], limit: int, *, prioritize_new_vocabulary: bool = False) -> list[Candidate]:
        shuffled = list(items)
        rng.shuffle(shuffled)
        shuffled.sort(key=lambda card: (card.last_practiced_at is not None, card.last_practiced_at or ""))
        selected = shuffled[:limit]
        if not prioritize_new_vocabulary:
            return selected

        vocabulary_positions = [
            index
            for index, card in enumerate(selected)
            if card.card_type == "vocabulary" and card.last_practiced_at is None
        ]
        ranked_vocabulary = sorted(
            (card for card in shuffled if card.card_type == "vocabulary" and card.last_practiced_at is None),
            key=lambda card: (card.frequency_rank is None, card.frequency_rank if card.frequency_rank is not None else 0),
        )
        for index, card in zip(vocabulary_positions, ranked_vocabulary):
            selected[index] = card
        return selected

    quota_12 = math.floor(0.7 * batch_size)
    quota_3 = batch_size - quota_12
    selected = take([card for card in candidates if card.score in (1, 2)], quota_12)
    selected.extend(take([card for card in candidates if card.score == 3], quota_3))
    if len(selected) < batch_size:
        selected.extend(
            take(
                [card for card in candidates if card.score == 0],
                min(5, batch_size - len(selected)),
                prioritize_new_vocabulary=True,
            )
        )
    rng.shuffle(selected)
    return selected


def _branch_options(form_parents: dict[str, str | None], base_word: str, target_form: str) -> list[str]:
    parent_form = form_parents[target_form]
    branch_parent = base_word if parent_form is None else parent_form
    return list(dict.fromkeys([branch_parent, *(form for form, parent in form_parents.items() if parent == branch_parent)]))


def _load_content(
    content_path: Path, progress_path: Path
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, set[str]], set[str], list[Candidate]]:
    with sqlite3.connect(content_path) as connection:
        connection.execute("ATTACH DATABASE ? AS progress", (str(progress_path),))
        vocabulary: dict[str, list[str]] = {}
        for word, meaning in connection.execute(
            """SELECT vocabulary.finnish, vocabulary_meanings.meaning
               FROM vocabulary JOIN vocabulary_meanings ON vocabulary.id = vocabulary_meanings.vocabulary_id
               ORDER BY vocabulary.id, vocabulary_meanings.ordinal"""
        ):
            vocabulary.setdefault(word, []).append(meaning)
        forms: dict[str, dict[str, str | None]] = {}
        for word, form, parent_form in connection.execute(
            """SELECT vocabulary.finnish, word_forms.form, word_forms.parent_form
               FROM vocabulary JOIN word_forms ON vocabulary.id = word_forms.vocabulary_id
               ORDER BY vocabulary.id, word_forms.id"""
        ):
            forms.setdefault(word, {})[form] = parent_form
        token_families: dict[str, set[str]] = {}
        for base_word, word_forms in forms.items():
            for form in word_forms:
                form_tokens = tokens(form)
                if len(form_tokens) == 1 and next(iter(form_tokens)) == form.casefold():
                    token_families.setdefault(form.casefold(), set()).add(base_word)
        mastered_families = {
            base_word
            for (base_word,) in connection.execute(
                """SELECT base_word FROM progress.card_progress
                   WHERE card_type = 'vocabulary' AND target_form = '' AND score = 3"""
            )
        }

        frequency_ranks = {
            token: rank for token, rank in connection.execute("SELECT token_casefold, frequency_rank FROM frequency_words")
        }
        candidates: list[Candidate] = []
        for word, score, last_practiced_at in connection.execute(
            """SELECT vocabulary.finnish, COALESCE(progress.card_progress.score, 0), progress.card_progress.last_practiced_at
               FROM vocabulary LEFT JOIN progress.card_progress
                 ON progress.card_progress.card_type = 'vocabulary'
                 AND progress.card_progress.base_word = vocabulary.finnish
                 AND progress.card_progress.target_form = ''"""
        ):
            candidates.append(Candidate("vocabulary", word, "", score, last_practiced_at, frequency_ranks.get(word.casefold())))
        for base_word, form, parent_form, score, last_practiced_at, vocabulary_score, parent_score in connection.execute(
            """SELECT vocabulary.finnish, word_forms.form, word_forms.parent_form,
                      COALESCE(form_progress.score, 0), form_progress.last_practiced_at,
                      COALESCE(vocabulary_progress.score, 0), COALESCE(parent_progress.score, 0)
               FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id
               LEFT JOIN progress.card_progress AS form_progress
                 ON form_progress.card_type = 'word_form'
                 AND form_progress.base_word = vocabulary.finnish
                 AND form_progress.target_form = word_forms.form
               LEFT JOIN progress.card_progress AS vocabulary_progress
                 ON vocabulary_progress.card_type = 'vocabulary'
                 AND vocabulary_progress.base_word = vocabulary.finnish
                 AND vocabulary_progress.target_form = ''
               LEFT JOIN progress.card_progress AS parent_progress
                 ON parent_progress.card_type = 'word_form'
                 AND parent_progress.base_word = vocabulary.finnish
                 AND parent_progress.target_form = word_forms.parent_form"""
        ):
            parent_is_mastered = vocabulary_score == 3 if parent_form is None or parent_form == base_word else parent_score == 3
            if (
                parent_is_mastered
                and _has_matching_sentence(connection, form)
                and len(_branch_options(forms[base_word], base_word, form)) >= 2
            ):
                candidates.append(Candidate("word_form", base_word, form, score, last_practiced_at))
    return vocabulary, forms, token_families, mastered_families, candidates


def _sentence_rows(connection: sqlite3.Connection, form: str) -> list[tuple[int, str]]:
    form_tokens = tokens(form)
    if len(form_tokens) == 1 and next(iter(form_tokens)) == form.casefold():
        return connection.execute(
            """SELECT sentences.id, sentences.finnish FROM sentence_tokens
               JOIN sentences ON sentences.id = sentence_tokens.sentence_id
               WHERE sentence_tokens.token_casefold = ?""",
            (form.casefold(),),
        ).fetchall()
    return connection.execute("SELECT id, finnish FROM sentences").fetchall()


def _has_matching_sentence(connection: sqlite3.Connection, form: str) -> bool:
    return any(matches_form(sentence, form) for _, sentence in _sentence_rows(connection, form))


def _sentence_weight(
    sentence: str,
    token_families: dict[str, set[str]],
    mastered_families: set[str],
    excluded_family: str | None = None,
) -> int:
    unmastered_families: set[str] = set()
    for token in tokens(sentence):
        families = token_families.get(token, set()) - {excluded_family}
        if families and not families.intersection(mastered_families):
            unmastered_families.update(families)
    return (16, 8, 4, 1)[min(len(unmastered_families), 3)]


def _matching_sentences(
    connection: sqlite3.Connection,
    form: str,
    token_families: dict[str, set[str]],
    mastered_families: set[str],
    target_family: str,
) -> tuple[list[tuple[str, list[str]]], list[int]]:
    matching: list[tuple[str, list[str]]] = []
    weights: list[int] = []
    for sentence_id, sentence in _sentence_rows(connection, form):
        if not matches_form(sentence, form):
            continue
        translations = [
            english
            for (english,) in connection.execute(
                "SELECT english FROM sentence_translations WHERE sentence_id = ? ORDER BY ordinal", (sentence_id,)
            )
        ]
        matching.append((sentence, translations))
        weights.append(_sentence_weight(sentence, token_families, mastered_families, target_family))
    return matching, weights


def _options(texts: list[str], correct_text: str, rng: random.Random) -> tuple[list[dict[str, str]], str]:
    options = [{"id": str(uuid.uuid4()), "text": text} for text in texts]
    correct_id = next(option["id"] for option in options if option["text"] == correct_text)
    rng.shuffle(options)
    return options, correct_id


def build_batch(content_path: Path, progress_path: Path, batch_size: int, rng: random.Random | None = None) -> list[dict[str, object]]:
    rng = rng or random.Random()
    vocabulary, forms, token_families, mastered_families, candidates = _load_content(content_path, progress_path)
    questions: list[dict[str, object]] = []
    with sqlite3.connect(content_path) as connection:
        for card in select_candidates(candidates, batch_size, rng):
            if card.card_type == "vocabulary":
                correct_text = " / ".join(vocabulary[card.base_word])
                distractors = list({" / ".join(meanings) for word, meanings in vocabulary.items() if word != card.base_word})
                rng.shuffle(distractors)
                options, correct_id = _options([correct_text, *distractors[:3]], correct_text, rng)
                prompt = card.base_word
                english_translations: list[str] = []
            else:
                matching_sentences, weights = _matching_sentences(
                    connection, card.target_form, token_families, mastered_families, card.base_word
                )
                sentence, english_translations = rng.choices(matching_sentences, weights=weights, k=1)[0]
                prompt = blank_form(sentence, card.target_form)
                branch_forms = _branch_options(forms[card.base_word], card.base_word, card.target_form)
                distractors = [form for form in dict.fromkeys(branch_forms) if form != card.target_form]
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
