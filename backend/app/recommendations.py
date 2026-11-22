from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from .sentences import tokens


_SQLITE_VARIABLE_LIMIT = 900


def _chunks(values: Iterable[int | str]) -> Iterable[list[int | str]]:
    chunk: list[int | str] = []
    for value in values:
        chunk.append(value)
        if len(chunk) == _SQLITE_VARIABLE_LIMIT:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _single_token(value: str) -> str | None:
    value_tokens = tokens(value)
    if len(value_tokens) != 1:
        return None
    token = next(iter(value_tokens))
    return token if token == value.casefold() else None


def get_recommendations(content_path: Path, limit: int = 20) -> list[dict[str, object]]:
    """Recommend common unknown tokens found beside tracked vocabulary families."""
    with sqlite3.connect(content_path) as connection:
        token_families: dict[str, set[str]] = defaultdict(set)
        for (base_word,) in connection.execute("SELECT finnish FROM vocabulary"):
            token = _single_token(base_word)
            if token is not None:
                token_families[token].add(base_word)
        for base_word, form in connection.execute(
            """SELECT vocabulary.finnish, word_forms.form
               FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id"""
        ):
            token = _single_token(form)
            if token is not None:
                token_families[token].add(base_word)
        if not token_families:
            return []

        sentence_families: dict[int, set[str]] = defaultdict(set)
        for token_chunk in _chunks(token_families):
            placeholders = ", ".join("?" for _ in token_chunk)
            for sentence_id, token in connection.execute(
                f"SELECT sentence_id, token_casefold FROM sentence_tokens WHERE token_casefold IN ({placeholders})",
                token_chunk,
            ):
                sentence_families[sentence_id].update(token_families[token])
        if not sentence_families:
            return []

        candidate_sentences: dict[str, set[int]] = defaultdict(set)
        for sentence_chunk in _chunks(sentence_families):
            placeholders = ", ".join("?" for _ in sentence_chunk)
            for sentence_id, token in connection.execute(
                f"SELECT sentence_id, token_casefold FROM sentence_tokens WHERE sentence_id IN ({placeholders})",
                sentence_chunk,
            ):
                if len(token) >= 3 and token not in token_families:
                    candidate_sentences[token].add(sentence_id)
        if not candidate_sentences:
            return []

        frequency_words: dict[str, tuple[int, int]] = {}
        for token_chunk in _chunks(candidate_sentences):
            placeholders = ", ".join("?" for _ in token_chunk)
            for token, rank, count in connection.execute(
                f"""SELECT token_casefold, frequency_rank, frequency_count
                    FROM frequency_words WHERE token_casefold IN ({placeholders})""",
                token_chunk,
            ):
                frequency_words[token] = (rank, count)

        has_lemma_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'recommendation_lemmas'"
        ).fetchone()
        lemma_mappings = {
            surface: lemma for surface, lemma in connection.execute("SELECT surface, lemma FROM recommendation_lemmas")
        } if has_lemma_table else {}

        grouped: dict[str, tuple[int, int, set[int], set[str], set[str]]] = {}
        for token, (rank, count) in frequency_words.items():
            word = lemma_mappings.get(token, token)
            sentence_ids = candidate_sentences[token]
            families = set().union(*(sentence_families[sentence_id] for sentence_id in sentence_ids))
            if word not in grouped:
                grouped[word] = (rank, count, set(sentence_ids), families, {token})
                continue
            best_rank, total_count, existing_sentences, existing_families, observed_forms = grouped[word]
            grouped[word] = (min(best_rank, rank), total_count + count, existing_sentences | sentence_ids, existing_families | families, observed_forms | {token})

        ranked = sorted(
            (
                (
                    word,
                    rank,
                    count,
                    sentence_ids,
                    families,
                    observed_forms,
                )
                for word, (rank, count, sentence_ids, families, observed_forms) in grouped.items()
            ),
            key=lambda candidate: (candidate[1], -len(candidate[4]), -len(candidate[3]), candidate[0]),
        )[:limit]
        if not ranked:
            return []

        example_ids = sorted({sentence_id for _, _, _, sentence_ids, _, _ in ranked for sentence_id in sorted(sentence_ids)[:2]})
        sentence_texts: dict[int, str] = {}
        translations: dict[int, list[str]] = defaultdict(list)
        for sentence_chunk in _chunks(example_ids):
            placeholders = ", ".join("?" for _ in sentence_chunk)
            for sentence_id, finnish in connection.execute(
                f"SELECT id, finnish FROM sentences WHERE id IN ({placeholders})", sentence_chunk
            ):
                sentence_texts[sentence_id] = finnish
            for sentence_id, english in connection.execute(
                f"""SELECT sentence_id, english FROM sentence_translations
                    WHERE sentence_id IN ({placeholders}) ORDER BY sentence_id, ordinal""",
                sentence_chunk,
            ):
                translations[sentence_id].append(english)

    return [
        {
            "word": word,
            "frequency_rank": rank,
            "frequency_count": count,
            "related_vocabulary_count": len(families),
            "observed_forms": sorted(form for form in observed_forms if form != word),
            "examples": [
                {"finnish": sentence_texts[sentence_id], "english_translations": translations[sentence_id]}
                for sentence_id in sorted(sentence_ids)[:2]
            ],
        }
        for word, rank, count, sentence_ids, families, observed_forms in ranked
    ]
