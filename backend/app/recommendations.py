from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from itertools import combinations
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


def _chain_relationships(
    candidates: list[tuple[str, int, int, set[int], set[str], set[str]]],
) -> dict[str, list[str]]:
    """Return directly co-occurring candidate words ordered by relationship strength."""
    sentence_words: dict[int, set[str]] = defaultdict(set)
    ranks = {word: rank for word, rank, *_ in candidates}
    for word, _, _, sentence_ids, _, _ in candidates:
        for sentence_id in sentence_ids:
            sentence_words[sentence_id].add(word)

    shared_counts: dict[tuple[str, str], int] = defaultdict(int)
    for words in sentence_words.values():
        for first, second in combinations(sorted(words), 2):
            shared_counts[(first, second)] += 1

    relationships: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (first, second), shared_count in shared_counts.items():
        relationships[first].append((second, shared_count))
        relationships[second].append((first, shared_count))
    return {
        word: [related for related, _ in sorted(related_words, key=lambda item: (-item[1], ranks[item[0]], item[0]))]
        for word, related_words in relationships.items()
    }


def _visible_recommendations(
    ranked: list[tuple[str, int, int, set[int], set[str], set[str]]],
    relationships: dict[str, list[str]],
    limit: int,
) -> list[tuple[str, int, int, set[int], set[str], set[str]]]:
    """Keep the strongest ranked results while making a few direct pairs visible."""
    visible = list(ranked[:limit])
    visible_words = {word for word, *_ in visible}
    promotions = 0
    for root, *_ in list(visible):
        if promotions == 3:
            break
        if root not in visible_words:
            continue
        companion = next((word for word in relationships.get(root, []) if word not in visible_words), None)
        if companion is None:
            continue
        connected = {
            word for word in visible_words
            if any(related in visible_words for related in relationships.get(word, []))
        }
        removable_indexes = [index for index, (word, *_) in enumerate(visible) if word not in connected]
        if not removable_indexes:
            break
        companion_candidate = next(candidate for candidate in ranked if candidate[0] == companion)
        removed = visible.pop(removable_indexes[-1])
        visible_words.remove(removed[0])
        visible.append(companion_candidate)
        visible_words.add(companion)
        promotions += 1
    return sorted(visible, key=lambda candidate: (candidate[1], -len(candidate[4]), -len(candidate[3]), candidate[0]))


def get_recommendations(content_path: Path, limit: int = 20) -> list[dict[str, object]]:
    """Recommend common unknown tokens found beside tracked vocabulary families."""
    with sqlite3.connect(content_path) as connection:
        token_families: dict[str, set[str]] = defaultdict(set)
        known_base_words: set[str] = set()
        for (base_word,) in connection.execute("SELECT finnish FROM vocabulary"):
            known_base_words.add(base_word.casefold())
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
            if word.casefold() in known_base_words:
                continue
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
        )
        if not ranked:
            return []

        relationships = _chain_relationships(ranked)
        ranked = _visible_recommendations(ranked, relationships, limit)
        visible_words = {word for word, *_ in ranked}

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
            "chain_words": [related for related in relationships.get(word, []) if related in visible_words][:1],
            "examples": [
                {"finnish": sentence_texts[sentence_id], "english_translations": translations[sentence_id]}
                for sentence_id in sorted(sentence_ids)[:2]
            ],
        }
        for word, rank, count, sentence_ids, families, observed_forms in ranked
    ]
