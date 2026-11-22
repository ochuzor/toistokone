from __future__ import annotations

import math
import random
import sqlite3
import uuid
from collections import defaultdict
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
    contextual_breadth: int = 0
    supporting_sentence_count: int = 0
    related_families: frozenset[str] = frozenset()
    reinforcement_quality: int = 0
    chain_families: frozenset[str] = frozenset()


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
        ranked_vocabulary = _select_diverse_new_vocabulary(
            [card for card in shuffled if card.card_type == "vocabulary" and card.last_practiced_at is None],
            len(vocabulary_positions),
        )
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


def _frequency_band(rank: int | None) -> int:
    if rank is None:
        return 4
    if rank <= 100:
        return 0
    if rank <= 500:
        return 1
    if rank <= 2_000:
        return 2
    return 3


def _new_vocabulary_key(card: Candidate, selected_families: frozenset[str]) -> tuple[int, int, int, int, int, int]:
    return (
        _frequency_band(card.frequency_rank),
        -card.contextual_breadth,
        -card.reinforcement_quality,
        -card.supporting_sentence_count,
        len(card.related_families.intersection(selected_families)),
        card.frequency_rank if card.frequency_rank is not None else 0,
    )


def _select_diverse_new_vocabulary(candidates: list[Candidate], limit: int) -> list[Candidate]:
    selected: list[Candidate] = []
    remaining = list(candidates)
    represented_families: frozenset[str] = frozenset()
    chain_companion_selected = False
    while remaining and len(selected) < limit:
        card = min(remaining, key=lambda candidate: _new_vocabulary_key(candidate, represented_families))
        selected.append(card)
        remaining.remove(card)
        represented_families = represented_families.union(card.related_families)
        if chain_companion_selected or len(selected) == limit:
            continue
        companions = [
            candidate for candidate in remaining
            if candidate.base_word in card.chain_families
            and _frequency_band(candidate.frequency_rank) == _frequency_band(card.frequency_rank)
        ]
        if not companions:
            continue
        companion = min(companions, key=lambda candidate: _new_vocabulary_key(candidate, represented_families))
        selected.append(companion)
        remaining.remove(companion)
        represented_families = represented_families.union(companion.related_families)
        chain_companion_selected = True
    return selected


def _profile_options(cards: list[FormCard], profile: str) -> list[str]:
    return list(dict.fromkeys(card.form for card in cards if card.profile == profile))


def _single_token(value: str) -> str | None:
    value_tokens = tokens(value)
    if len(value_tokens) != 1:
        return None
    token = next(iter(value_tokens))
    return token if token == value.casefold() else None


def _context_support(connection: sqlite3.Connection, token_families: dict[str, set[str]], mastered_families: set[str]) -> dict[str, tuple[int, int, frozenset[str], int]]:
    """Return contextual support and mastery-aware reinforcement quality for each word family."""
    sentence_families: dict[int, set[str]] = {}
    sentence_token_families: dict[int, list[set[str]]] = {}
    token_list = list(token_families)
    for start in range(0, len(token_list), 900):
        token_chunk = token_list[start:start + 900]
        placeholders = ", ".join("?" for _ in token_chunk)
        for sentence_id, token in connection.execute(
            f"SELECT sentence_id, token_casefold FROM sentence_tokens WHERE token_casefold IN ({placeholders})",
            token_chunk,
        ):
            sentence_families.setdefault(sentence_id, set()).update(token_families[token])
            sentence_token_families.setdefault(sentence_id, []).append(token_families[token])

    sentence_counts: dict[str, set[int]] = {}
    related_families: dict[str, set[str]] = {}
    reinforcement_quality: dict[str, int] = {}
    for sentence_id, families in sentence_families.items():
        for family in families:
            sentence_counts.setdefault(family, set()).add(sentence_id)
            related_families.setdefault(family, set()).update(families - {family})
            unmastered_families: set[str] = set()
            for token_family_set in sentence_token_families[sentence_id]:
                other_families = token_family_set - {family}
                if other_families and not other_families.intersection(mastered_families):
                    unmastered_families.update(other_families)
            reinforcement_quality[family] = reinforcement_quality.get(family, 0) + _reinforcement_weight(len(unmastered_families))
    return {
        family: (
            len(related_families.get(family, set())),
            len(sentence_counts.get(family, set())),
            frozenset(related_families.get(family, set())),
            reinforcement_quality.get(family, 0),
        )
        for families in token_families.values()
        for family in families
    }


def _direct_chain_families(connection: sqlite3.Connection, token_families: dict[str, set[str]]) -> dict[str, frozenset[str]]:
    """Return vocabulary families that directly co-occur in imported sentences."""
    sentence_families: dict[int, set[str]] = defaultdict(set)
    token_list = list(token_families)
    for start in range(0, len(token_list), 900):
        token_chunk = token_list[start:start + 900]
        placeholders = ", ".join("?" for _ in token_chunk)
        for sentence_id, token in connection.execute(
            f"SELECT sentence_id, token_casefold FROM sentence_tokens WHERE token_casefold IN ({placeholders})",
            token_chunk,
        ):
            sentence_families[sentence_id].update(token_families[token])
    related: dict[str, set[str]] = defaultdict(set)
    for families in sentence_families.values():
        for family in families:
            related[family].update(families - {family})
    return {family: frozenset(other_families) for family, other_families in related.items()}


def _load_content(content_path: Path, progress_path: Path) -> tuple[dict[str, list[str]], dict[str, list[FormCard]], dict[str, set[str]], set[str], list[Candidate]]:
    with sqlite3.connect(content_path) as connection:
        connection.execute("ATTACH DATABASE ? AS progress", (str(progress_path),))
        vocabulary: dict[str, list[str]] = {}
        for word, meaning in connection.execute("SELECT vocabulary.finnish, vocabulary_meanings.meaning FROM vocabulary JOIN vocabulary_meanings ON vocabulary.id = vocabulary_meanings.vocabulary_id ORDER BY vocabulary.id, vocabulary_meanings.ordinal"):
            vocabulary.setdefault(word, []).append(meaning)
        forms: dict[str, list[FormCard]] = {}
        for word, card_key, form, profile, prompt_label in connection.execute("SELECT vocabulary.finnish, word_forms.card_key, word_forms.form, word_forms.profile, word_forms.prompt_label FROM vocabulary JOIN word_forms ON vocabulary.id = word_forms.vocabulary_id ORDER BY vocabulary.id, word_forms.id"):
            forms.setdefault(word, []).append(FormCard(card_key, form, profile, prompt_label))
        token_families: dict[str, set[str]] = {}
        contextual_token_families: dict[str, set[str]] = {}
        for base_word in vocabulary:
            token = _single_token(base_word)
            if token is not None:
                contextual_token_families.setdefault(token, set()).add(base_word)
        for base_word, form_cards in forms.items():
            for form_card in form_cards:
                token = _single_token(form_card.form)
                if token is not None:
                    token_families.setdefault(token, set()).add(base_word)
                    contextual_token_families.setdefault(token, set()).add(base_word)
        mastered_families = {
            base_word for (base_word,) in connection.execute(
                "SELECT base_word FROM progress.card_progress WHERE card_type = 'vocabulary' AND target_form = '' AND score = 3"
            )
        }
        context_support = _context_support(connection, contextual_token_families, mastered_families)
        direct_chain_families = _direct_chain_families(connection, contextual_token_families)
        frequency_ranks = {token: rank for token, rank in connection.execute("SELECT token_casefold, frequency_rank FROM frequency_words")}
        candidates: list[Candidate] = []
        for word, score, last_practiced_at in connection.execute("SELECT vocabulary.finnish, COALESCE(progress.card_progress.score, 0), progress.card_progress.last_practiced_at FROM vocabulary LEFT JOIN progress.card_progress ON progress.card_progress.card_type = 'vocabulary' AND progress.card_progress.base_word = vocabulary.finnish AND progress.card_progress.target_form = ''"):
            breadth, sentence_count, related_families, reinforcement_quality = context_support.get(word, (0, 0, frozenset(), 0))
            candidates.append(Candidate("vocabulary", word, "", score, last_practiced_at, frequency_ranks.get(word.casefold()), breadth, sentence_count, related_families, reinforcement_quality, direct_chain_families.get(word, frozenset())))
        for base_word, card_key, profile, score, last_practiced_at, vocabulary_score in connection.execute("SELECT vocabulary.finnish, word_forms.card_key, word_forms.profile, COALESCE(form_progress.score, 0), form_progress.last_practiced_at, COALESCE(vocabulary_progress.score, 0) FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id LEFT JOIN progress.card_progress AS form_progress ON form_progress.card_type = 'word_form' AND form_progress.base_word = vocabulary.finnish AND form_progress.target_form = word_forms.card_key LEFT JOIN progress.card_progress AS vocabulary_progress ON vocabulary_progress.card_type = 'vocabulary' AND vocabulary_progress.base_word = vocabulary.finnish AND vocabulary_progress.target_form = ''"):
            if vocabulary_score == 3 and len(_profile_options(forms[base_word], profile)) >= 2:
                candidates.append(Candidate("word_form", base_word, card_key, score, last_practiced_at))
    return vocabulary, forms, token_families, mastered_families, candidates


def _sentence_weight(sentence: str, token_families: dict[str, set[str]], mastered_families: set[str], excluded_family: str | None = None) -> int:
    unmastered_families: set[str] = set()
    for token in tokens(sentence):
        families = token_families.get(token, set()) - {excluded_family}
        if families and not families.intersection(mastered_families):
            unmastered_families.update(families)
    return _reinforcement_weight(len(unmastered_families))


def _reinforcement_weight(unmastered_family_count: int) -> int:
    return (16, 8, 4, 1)[min(unmastered_family_count, 3)]


def _matching_sentences(
    connection: sqlite3.Connection,
    form: str,
    token_families: dict[str, set[str]],
    mastered_families: set[str],
    target_family: str,
) -> tuple[list[tuple[str, list[str]]], list[int]]:
    form_tokens = tokens(form)
    if len(form_tokens) != 1 or next(iter(form_tokens)) != form.casefold():
        return [], []
    rows = connection.execute(
        """SELECT sentences.id, sentences.finnish FROM sentence_tokens
           JOIN sentences ON sentences.id = sentence_tokens.sentence_id
           WHERE sentence_tokens.token_casefold = ?""",
        (form.casefold(),),
    ).fetchall()
    matching: list[tuple[str, list[str]]] = []
    weights: list[int] = []
    for sentence_id, sentence in rows:
        if not matches_form(sentence, form):
            continue
        translations = [english for (english,) in connection.execute(
            "SELECT english FROM sentence_translations WHERE sentence_id = ? ORDER BY ordinal", (sentence_id,)
        )]
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
                prompt, english_translations = card.base_word, []
            else:
                form_card = next(form for form in forms[card.base_word] if form.card_key == card.target_form)
                branch_forms = _profile_options(forms[card.base_word], form_card.profile)
                distractors = [form for form in branch_forms if form != form_card.form]
                rng.shuffle(distractors)
                options, correct_id = _options([form_card.form, *distractors[:3]], form_card.form, rng)
                prompt, english_translations = f"{card.base_word} — {form_card.prompt_label}", []
                if card.score == 3:
                    matching, weights = _matching_sentences(connection, form_card.form, token_families, mastered_families, card.base_word)
                    if matching:
                        sentence, english_translations = rng.choices(matching, weights=weights, k=1)[0]
                        prompt = blank_form(sentence, form_card.form)
            questions.append({"question_id": str(uuid.uuid4()), "card": {"type": card.card_type, "base_word": card.base_word, "target_form": card.target_form}, "score": card.score, "prompt": prompt, "english_translations": english_translations, "options": options, "correct_option_id": correct_id})
    return questions
