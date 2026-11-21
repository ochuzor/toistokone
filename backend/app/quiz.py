from __future__ import annotations

import math
import random
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .sentences import tokens


@dataclass(frozen=True)
class Candidate:
    card_type: str
    base_word: str
    target_form: str
    score: int
    last_practiced_at: str | None
    frequency_rank: int | None = None


@dataclass(frozen=True)
class FormCard:
    card_key: str
    form: str
    profile: str
    prompt_label: str


def select_candidates(candidates: list[Candidate], batch_size: int, rng: random.Random) -> list[Candidate]:
    """Apply the PRD's non-backfilling 70/30/up-to-five-new selection rule."""
    def take(items: list[Candidate], limit: int, *, prioritize_new_vocabulary: bool = False) -> list[Candidate]:
        shuffled = list(items)
        rng.shuffle(shuffled)
        shuffled.sort(key=lambda card: (card.last_practiced_at is not None, card.last_practiced_at or ""))
        selected = shuffled[:limit]
        if not prioritize_new_vocabulary:
            return selected
        vocabulary_positions = [index for index, card in enumerate(selected) if card.card_type == "vocabulary" and card.last_practiced_at is None]
        ranked_vocabulary = sorted((card for card in shuffled if card.card_type == "vocabulary" and card.last_practiced_at is None), key=lambda card: (card.frequency_rank is None, card.frequency_rank if card.frequency_rank is not None else 0))
        for index, card in zip(vocabulary_positions, ranked_vocabulary):
            selected[index] = card
        return selected

    quota_12 = math.floor(0.7 * batch_size)
    quota_3 = batch_size - quota_12
    selected = take([card for card in candidates if card.score in (1, 2)], quota_12)
    selected.extend(take([card for card in candidates if card.score == 3], quota_3))
    if len(selected) < batch_size:
        selected.extend(take([card for card in candidates if card.score == 0], min(5, batch_size - len(selected)), prioritize_new_vocabulary=True))
    rng.shuffle(selected)
    return selected


def _profile_options(cards: list[FormCard], profile: str) -> list[str]:
    return list(dict.fromkeys(card.form for card in cards if card.profile == profile))


def _load_content(content_path: Path, progress_path: Path) -> tuple[dict[str, list[str]], dict[str, list[FormCard]], list[Candidate]]:
    with sqlite3.connect(content_path) as connection:
        connection.execute("ATTACH DATABASE ? AS progress", (str(progress_path),))
        vocabulary: dict[str, list[str]] = {}
        for word, meaning in connection.execute("SELECT vocabulary.finnish, vocabulary_meanings.meaning FROM vocabulary JOIN vocabulary_meanings ON vocabulary.id = vocabulary_meanings.vocabulary_id ORDER BY vocabulary.id, vocabulary_meanings.ordinal"):
            vocabulary.setdefault(word, []).append(meaning)
        forms: dict[str, list[FormCard]] = {}
        for word, card_key, form, profile, prompt_label in connection.execute("SELECT vocabulary.finnish, word_forms.card_key, word_forms.form, word_forms.profile, word_forms.prompt_label FROM vocabulary JOIN word_forms ON vocabulary.id = word_forms.vocabulary_id ORDER BY vocabulary.id, word_forms.id"):
            forms.setdefault(word, []).append(FormCard(card_key, form, profile, prompt_label))
        frequency_ranks = {token: rank for token, rank in connection.execute("SELECT token_casefold, frequency_rank FROM frequency_words")}
        candidates: list[Candidate] = []
        for word, score, last_practiced_at in connection.execute("SELECT vocabulary.finnish, COALESCE(progress.card_progress.score, 0), progress.card_progress.last_practiced_at FROM vocabulary LEFT JOIN progress.card_progress ON progress.card_progress.card_type = 'vocabulary' AND progress.card_progress.base_word = vocabulary.finnish AND progress.card_progress.target_form = ''"):
            candidates.append(Candidate("vocabulary", word, "", score, last_practiced_at, frequency_ranks.get(word.casefold())))
        for base_word, card_key, profile, score, last_practiced_at, vocabulary_score in connection.execute("SELECT vocabulary.finnish, word_forms.card_key, word_forms.profile, COALESCE(form_progress.score, 0), form_progress.last_practiced_at, COALESCE(vocabulary_progress.score, 0) FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id LEFT JOIN progress.card_progress AS form_progress ON form_progress.card_type = 'word_form' AND form_progress.base_word = vocabulary.finnish AND form_progress.target_form = word_forms.card_key LEFT JOIN progress.card_progress AS vocabulary_progress ON vocabulary_progress.card_type = 'vocabulary' AND vocabulary_progress.base_word = vocabulary.finnish AND vocabulary_progress.target_form = ''"):
            if vocabulary_score == 3 and len(_profile_options(forms[base_word], profile)) >= 2:
                candidates.append(Candidate("word_form", base_word, card_key, score, last_practiced_at))
    return vocabulary, forms, candidates


def _sentence_weight(sentence: str, token_families: dict[str, set[str]], mastered_families: set[str], excluded_family: str | None = None) -> int:
    unmastered_families: set[str] = set()
    for token in tokens(sentence):
        families = token_families.get(token, set()) - {excluded_family}
        if families and not families.intersection(mastered_families):
            unmastered_families.update(families)
    return (16, 8, 4, 1)[min(len(unmastered_families), 3)]


def _options(texts: list[str], correct_text: str, rng: random.Random) -> tuple[list[dict[str, str]], str]:
    options = [{"id": str(uuid.uuid4()), "text": text} for text in texts]
    correct_id = next(option["id"] for option in options if option["text"] == correct_text)
    rng.shuffle(options)
    return options, correct_id


def build_batch(content_path: Path, progress_path: Path, batch_size: int, rng: random.Random | None = None) -> list[dict[str, object]]:
    rng = rng or random.Random()
    vocabulary, forms, candidates = _load_content(content_path, progress_path)
    questions: list[dict[str, object]] = []
    for card in select_candidates(candidates, batch_size, rng):
        if card.card_type == "vocabulary":
            correct_text = " / ".join(vocabulary[card.base_word])
            distractors = list({" / ".join(meanings) for word, meanings in vocabulary.items() if word != card.base_word})
            rng.shuffle(distractors)
            options, correct_id = _options([correct_text, *distractors[:3]], correct_text, rng)
            prompt, english_translations = card.base_word, []
        else:
            form_card = next(form for form in forms[card.base_word] if form.card_key == card.target_form)
            branch_forms = _profile_options(forms[card.base_word], form_card.profile)
            distractors = [form for form in branch_forms if form != form_card.form]
            rng.shuffle(distractors)
            options, correct_id = _options([form_card.form, *distractors[:3]], form_card.form, rng)
            prompt, english_translations = f"{card.base_word} — {form_card.prompt_label}", []
        questions.append({"question_id": str(uuid.uuid4()), "card": {"type": card.card_type, "base_word": card.base_word, "target_form": card.target_form}, "score": card.score, "prompt": prompt, "english_translations": english_translations, "options": options, "correct_option_id": correct_id})
    return questions
