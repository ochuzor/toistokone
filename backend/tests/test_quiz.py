from __future__ import annotations

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app.db import initialize_progress_database, record_answer
from backend.app.models import CardReference
from backend.app.quiz import Candidate, _context_support, _sentence_weight, build_batch, select_candidates
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

            support = _context_support(connection, {"auto": {"auto"}, "talo": {"talo"}})

        self.assertEqual(support["auto"], (1, 2, frozenset({"talo"})))
        self.assertEqual(support["talo"], (1, 1, frozenset({"auto"})))


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
        questions = build_batch(self.content, self.progress, 20, random.Random(3))
        inessive = next(question for question in questions if question["card"]["target_form"] == "nominal:inessive")
        verb = next(question for question in questions if question["card"]["target_form"] == "verb:present-3sg")
        self.assertEqual(inessive["prompt"], "talo — Inessiivi (missä?)")
        self.assertEqual(verb["prompt"], "tehdä — hän ____")
        self.assertIn("talossa", {option["text"] for option in inessive["options"]})
        self.assertEqual(len(inessive["options"]), 4)
        self.assertEqual(verb["english_translations"], [])

        self.master_form("talo", "nominal:inessive")
        self.master_form("tehdä", "verb:present-3sg")
        questions = build_batch(self.content, self.progress, 20, random.Random(3))
        inessive = next(question for question in questions if question["card"]["target_form"] == "nominal:inessive")
        verb = next(question for question in questions if question["card"]["target_form"] == "verb:present-3sg")
        self.assertEqual(inessive["prompt"], "____ asun.")
        self.assertEqual(inessive["english_translations"], ["I live in the house."])
        self.assertEqual(verb["prompt"], "tehdä — hän ____")
        self.assertEqual(verb["english_translations"], [])


if __name__ == "__main__":
    unittest.main()
