from __future__ import annotations

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app.db import initialize_progress_database, list_focus_words, record_answer, request_focus_word
from backend.app.models import CardReference
from backend.app.quiz import Candidate, _context_support, _load_content, _select_diverse_new_vocabulary, _select_new_forms, _sentence_weight, build_batch, select_candidates
from backend.pipeline import run_import
from backend.tests.kaikki_fixture import write_kaikki


class SentenceWeightTests(unittest.TestCase):
    def test_sentence_weight_counts_unmastered_families_once(self) -> None:
        families = {"tuttu": {"tuttu"}, "uusi": {"uusi"}, "toinen": {"toinen"}, "kolmas": {"kolmas"}}
        self.assertEqual(_sentence_weight("Tuttu uusi toinen kolmas.", families, {"tuttu"}), 1)


class ContextSupportTests(unittest.TestCase):
    def test_context_support_excludes_a_word_family_from_its_own_breadth(self) -> None:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE sentence_tokens (sentence_id INTEGER, token_casefold TEXT)")
            connection.executemany(
                "INSERT INTO sentence_tokens VALUES (?, ?)",
                [(1, "auto"), (2, "auto"), (2, "talo")],
            )

            support = _context_support(connection, {"auto": {"auto"}, "talo": {"talo"}}, set())

        self.assertEqual(support["auto"], (1, 2, frozenset({"talo"}), 24))
        self.assertEqual(support["talo"], (1, 1, frozenset({"auto"}), 8))

    def test_context_support_rewards_sentences_with_mastered_families(self) -> None:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE sentence_tokens (sentence_id INTEGER, token_casefold TEXT)")
            connection.executemany(
                "INSERT INTO sentence_tokens VALUES (?, ?)",
                [(1, "target"), (1, "known"), (2, "target"), (2, "unknown")],
            )

            support = _context_support(
                connection,
                {"target": {"target"}, "known": {"known"}, "unknown": {"unknown"}},
                {"known"},
            )

        self.assertEqual(support["target"][3], 24)


class QuizSelectionTests(unittest.TestCase):
    def test_new_vocabulary_uses_frequency_rank_without_changing_mix(self) -> None:
        candidates = [Candidate("vocabulary", "unranked", "", 0, None), Candidate("vocabulary", "rank-two", "", 0, None, 2), Candidate("vocabulary", "rank-one", "", 0, None, 1), Candidate("word_form", "root", "form", 0, None)]
        selected = select_candidates(candidates, 4, random.Random(7))
        self.assertEqual(sum(card.card_type == "vocabulary" for card in selected), 3)
        self.assertEqual({card.frequency_rank for card in selected if card.card_type == "vocabulary"}, {1, 2, None})

    def test_new_vocabulary_uses_context_within_a_frequency_band(self) -> None:
        candidates = [
            Candidate("vocabulary", "frequent", "", 0, None, 200, 0, 0),
            Candidate("vocabulary", "contextual", "", 0, None, 300, 3, 2),
            Candidate("vocabulary", "some-context", "", 0, None, 400, 2, 3),
        ]

        selected = select_candidates(candidates, 2, random.Random(7))

        self.assertEqual({card.base_word for card in selected}, {"contextual", "some-context"})

    def test_new_vocabulary_keeps_higher_frequency_bands_first(self) -> None:
        candidates = [
            Candidate("vocabulary", "very-common", "", 0, None, 100, 0, 0),
            Candidate("vocabulary", "contextual", "", 0, None, 101, 10, 10),
        ]

        selected = select_candidates(candidates, 1, random.Random(7))

        self.assertEqual(selected[0].base_word, "very-common")

    def test_new_vocabulary_prefers_reinforcement_quality_after_contextual_breadth(self) -> None:
        candidates = [
            Candidate("vocabulary", "more-sentences", "", 0, None, 200, 2, 3, frozenset(), 12),
            Candidate("vocabulary", "reinforcement-ready", "", 0, None, 300, 2, 1, frozenset(), 16),
        ]

        selected = select_candidates(candidates, 1, random.Random(7))

        self.assertEqual(selected[0].base_word, "reinforcement-ready")

    def test_new_vocabulary_prefers_a_different_context_neighborhood_after_relevance(self) -> None:
        candidates = [
            Candidate("vocabulary", "first", "", 0, None, 200, 2, 2, frozenset({"auto", "talo"})),
            Candidate("vocabulary", "overlapping", "", 0, None, 300, 2, 2, frozenset({"auto", "talo"})),
            Candidate("vocabulary", "diverse", "", 0, None, 400, 2, 2, frozenset({"ruoka", "ravintola"})),
        ]

        selected = select_candidates(candidates, 2, random.Random(7))

        self.assertEqual({card.base_word for card in selected}, {"first", "diverse"})

    def test_new_vocabulary_does_not_exclude_shared_neighborhoods(self) -> None:
        candidates = [
            Candidate("vocabulary", "first", "", 0, None, 200, 2, 2, frozenset({"auto"})),
            Candidate("vocabulary", "second", "", 0, None, 300, 2, 2, frozenset({"auto"})),
        ]

        selected = select_candidates(candidates, 2, random.Random(7))

        self.assertEqual({card.base_word for card in selected}, {"first", "second"})

    def test_new_vocabulary_adds_one_same_band_direct_companion_then_resumes_diversity(self) -> None:
        candidates = [
            Candidate("vocabulary", "first", "", 0, None, 200, 3, 3, frozenset({"auto"}), 10, frozenset({"companion"})),
            Candidate("vocabulary", "companion", "", 0, None, 300, 0, 0, frozenset({"auto"}), 0, frozenset({"first"})),
            Candidate("vocabulary", "diverse", "", 0, None, 400, 2, 2, frozenset({"ruoka"}), 5),
        ]

        selected = select_candidates(candidates, 3, random.Random(7))

        self.assertEqual({card.base_word for card in selected}, {"first", "companion", "diverse"})

    def test_new_vocabulary_does_not_promote_a_companion_from_a_lower_frequency_band(self) -> None:
        candidates = [
            Candidate("vocabulary", "first", "", 0, None, 100, 0, 0, frozenset(), 0, frozenset({"lower-band"})),
            Candidate("vocabulary", "lower-band", "", 0, None, 101, 0, 0, frozenset(), 0, frozenset({"first"})),
            Candidate("vocabulary", "contextual", "", 0, None, 102, 1, 1),
        ]

        selected = select_candidates(candidates, 2, random.Random(7))

        self.assertEqual({card.base_word for card in selected}, {"first", "contextual"})

    def test_focus_requests_take_vocabulary_slots_in_request_order(self) -> None:
        candidates = [
            Candidate("vocabulary", "ordinary", "", 0, None, 1),
            Candidate("vocabulary", "newer-focus", "", 0, None, 2, focus_requested_at="2026-01-02T00:00:00+00:00"),
            Candidate("vocabulary", "older-focus", "", 0, None, 3, focus_requested_at="2026-01-01T00:00:00+00:00"),
        ]

        selected = _select_diverse_new_vocabulary(candidates, 2)

        self.assertEqual([card.base_word for card in selected], ["older-focus", "newer-focus"])

    def test_focus_requests_are_not_displaced_by_a_chain_companion(self) -> None:
        candidates = [
            Candidate("vocabulary", "focus-one", "", 0, None, 100, chain_families=frozenset({"companion"}), focus_requested_at="2026-01-01T00:00:00+00:00"),
            Candidate("vocabulary", "companion", "", 0, None, 100),
            Candidate("vocabulary", "focus-two", "", 0, None, 100, focus_requested_at="2026-01-02T00:00:00+00:00"),
        ]

        selected = _select_diverse_new_vocabulary(candidates, 2)

        self.assertEqual([card.base_word for card in selected], ["focus-one", "focus-two"])

    def test_new_forms_are_selected_by_frequency_before_unranked_forms(self) -> None:
        candidates = [
            Candidate("word_form", "olla", "present-3sg", 0, None, 9),
            Candidate("word_form", "olla", "present-1pl", 0, None, 500),
            Candidate("word_form", "olla", "present-2pl", 0, None),
        ]

        selected = _select_new_forms(candidates, 3, random.Random(7))

        self.assertEqual([card.target_form for card in selected], ["present-3sg", "present-1pl", "present-2pl"])

    def test_new_form_ranking_preserves_the_selected_card_type_mix(self) -> None:
        candidates = [
            Candidate("vocabulary", f"word-{index}", "", 0, None, 100 + index)
            for index in range(4)
        ] + [
            Candidate("word_form", "olla", "present-3sg", 0, None, 1),
            Candidate("word_form", "olla", "present-1sg", 0, None, 2),
            Candidate("word_form", "olla", "present-1pl", 0, None, 3),
            Candidate("word_form", "olla", "present-2pl", 0, None, 4),
        ]
        expected_initial = list(candidates)
        random.Random(11).shuffle(expected_initial)

        selected = select_candidates(candidates, 5, random.Random(11))

        self.assertEqual(
            sum(card.card_type == "word_form" for card in selected),
            sum(card.card_type == "word_form" for card in expected_initial[:5]),
        )
        selected_form_ranks = sorted(card.frequency_rank for card in selected if card.card_type == "word_form")
        self.assertEqual(selected_form_ranks, list(range(1, len(selected_form_ranks) + 1)))


class GrammarBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "sentences").mkdir()
        (self.root / "frequency").mkdir()
        (self.root / "frequency" / "fi_50k.txt").write_text("talo 100\ntehdä 90\n", encoding="utf-8")
        (self.root / "dictionary.txt").write_text("talo - house\ntehdä - to do\n", encoding="utf-8")
        (self.root / "sentences" / "lesson.txt").write_text("Talossa asun. - I live in the house.\n", encoding="utf-8")
        write_kaikki(self.root)
        run_import(self.root)
        self.content = self.root / "data" / "content.sqlite"
        self.progress = self.root / "data" / "progress.sqlite"
        initialize_progress_database(self.progress)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def master(self, word: str) -> None:
        for attempt in range(3):
            record_answer(self.progress, CardReference(type="vocabulary", base_word=word), f"{word}-{attempt}", True, cooldown_minutes=0)

    def master_form(self, word: str, card_key: str) -> None:
        for attempt in range(3):
            record_answer(self.progress, CardReference(type="word_form", base_word=word, target_form=card_key), f"{word}-{card_key}-{attempt}", True, cooldown_minutes=0)

    def test_mastered_forms_use_contextual_sentences_and_fall_back_to_grammar_prompts(self) -> None:
        before = build_batch(self.content, self.progress, 20, random.Random(3))
        self.assertFalse(any(question["card"]["type"] == "word_form" for question in before))
        self.master("talo")
        self.master("tehdä")
        _, _, _, _, candidates = _load_content(self.content, self.progress)
        self.assertTrue(any(
            candidate.card_type == "word_form"
            and candidate.base_word == "talo"
            and candidate.target_form == "nominal:nominative-plural"
            for candidate in candidates
        ))
        questions = build_batch(self.content, self.progress, 20, random.Random(3))
        inessive = next(question for question in questions if question["card"]["target_form"] == "nominal:inessive")
        verb = next(question for question in questions if question["card"]["target_form"] == "verb:present-3sg")
        self.assertEqual(inessive["hint"], "talo")
        self.assertEqual(inessive["prompt"], "Inessiivi (missä?)")
        self.assertEqual(verb["hint"], "tehdä")
        self.assertEqual(verb["prompt"], "hän ____")
        self.assertIn("talossa", {option["text"] for option in inessive["options"]})
        self.assertEqual(len(inessive["options"]), 4)
        self.assertEqual(verb["english_translations"], [])

        self.master_form("talo", "nominal:inessive")
        self.master_form("tehdä", "verb:present-3sg")
        questions = build_batch(self.content, self.progress, 20, random.Random(3))
        inessive = next(question for question in questions if question["card"]["target_form"] == "nominal:inessive")
        verb = next(question for question in questions if question["card"]["target_form"] == "verb:present-3sg")
        self.assertEqual(inessive["prompt"], "____ asun.")
        self.assertIsNone(inessive["hint"])
        self.assertEqual(inessive["english_translations"], ["I live in the house."])
        self.assertEqual(verb["hint"], "tehdä")
        self.assertEqual(verb["prompt"], "hän ____")
        self.assertEqual(verb["english_translations"], [])

    def test_focus_request_is_consumed_only_when_its_card_enters_a_batch(self) -> None:
        request_focus_word(self.content, self.progress, "talo")

        questions = build_batch(self.content, self.progress, 20, random.Random(3))

        self.assertTrue(any(question["card"] == {"type": "vocabulary", "base_word": "talo", "target_form": ""} for question in questions))
        self.assertEqual(list_focus_words(self.content, self.progress), [])


if __name__ == "__main__":
    unittest.main()
