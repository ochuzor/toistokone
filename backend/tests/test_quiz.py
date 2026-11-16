from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from backend.app.db import initialize_progress_database, record_answer, reset_card
from backend.app.models import CardReference
from backend.app.quiz import Candidate, _sentence_weight, build_batch, select_candidates
from backend.app.sentences import blank_form, matches_form
from backend.pipeline import run_import


class SentenceMatchingTests(unittest.TestCase):
    def test_matches_unicode_whole_words_and_blanks_every_occurrence(self) -> None:
        sentence = "Äiti syö ruokaa, ja ruokaa jää pöydälle."
        self.assertTrue(matches_form(sentence, "ruokaa"))
        self.assertFalse(matches_form("ruokaakin syödään", "ruokaa"))
        self.assertEqual(blank_form(sentence, "ruokaa"), "Äiti syö ____, ja ____ jää pöydälle.")

    def test_matching_is_case_insensitive_without_matching_substrings(self) -> None:
        self.assertTrue(matches_form("RUOKAA on.", "ruokaa"))
        self.assertFalse(matches_form("ruokaaikaa", "ruokaa"))

    def test_sentence_weight_counts_unmastered_families_once(self) -> None:
        token_families = {
            "tuttu": {"tuttu"},
            "uusi": {"uusi"},
            "toinen": {"toinen"},
            "kolmas": {"kolmas"},
        }
        mastered = {"tuttu"}

        self.assertEqual(_sentence_weight("Tuttu.", token_families, mastered), 16)
        self.assertEqual(_sentence_weight("Tuttu uusi.", token_families, mastered), 8)
        self.assertEqual(_sentence_weight("Tuttu uusi toinen.", token_families, mastered), 4)
        self.assertEqual(_sentence_weight("Tuttu uusi toinen kolmas.", token_families, mastered), 1)
        self.assertEqual(_sentence_weight("Uusi uusi.", token_families, mastered), 8)
        self.assertEqual(_sentence_weight("Uusi.", token_families, set(), "uusi"), 16)


class QuizSelectionTests(unittest.TestCase):
    def cards(self, score: int, count: int, prefix: str) -> list[Candidate]:
        return [Candidate("vocabulary", f"{prefix}{index}", "", score, None) for index in range(count)]

    def test_strict_quota_examples(self) -> None:
        examples = [
            ((20, 20, 20), (14, 6, 0)),
            ((8, 20, 20), (8, 6, 5)),
            ((20, 2, 20), (14, 2, 4)),
            ((5, 3, 2), (5, 3, 2)),
            ((0, 0, 20), (0, 0, 5)),
        ]
        for (count_12, count_3, count_0), expected in examples:
            with self.subTest(available=(count_12, count_3, count_0)):
                selected = select_candidates(
                    self.cards(1, count_12, "one") + self.cards(3, count_3, "three") + self.cards(0, count_0, "zero"),
                    20,
                    random.Random(1),
                )
                counts = tuple(sum(card.score == score for card in selected) for score in (1, 3, 0))
                self.assertEqual(counts, expected)

    def test_never_practiced_cards_precede_practiced_cards(self) -> None:
        selected = select_candidates(
            [
                Candidate("vocabulary", "old", "", 1, "2026-01-01T00:00:00+00:00"),
                Candidate("vocabulary", "new", "", 1, None),
            ],
            2,
            random.Random(2),
        )
        self.assertEqual(selected[0].base_word, "new")


class BatchConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "sentences").mkdir()
        (self.root / "dictionary.txt").write_text("ruoka - food / meal\ntalo - house\n", encoding="utf-8")
        (self.root / "word-forms.txt").write_text("ruoka - ruokaa / ruoassa\n", encoding="utf-8")
        (self.root / "sentences" / "lesson.txt").write_text(
            "Ruokaa on, ruokaa! - There is food. / Food exists.\nTalo on suuri. - The house is big.\n",
            encoding="utf-8",
        )
        run_import(self.root)
        self.content = self.root / "data" / "content.sqlite"
        self.progress = self.root / "data" / "progress.sqlite"
        initialize_progress_database(self.progress)
        food = CardReference(type="vocabulary", base_word="ruoka")
        for attempt_id in ("food-1", "food-2", "food-3"):
            record_answer(self.progress, food, attempt_id, True, cooldown_minutes=0)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_word_forms_unlock_only_when_parent_is_mastered_and_question_is_formatted(self) -> None:
        questions = build_batch(self.content, self.progress, 10, random.Random(3))
        food_form = next(question for question in questions if question["card"]["type"] == "word_form" and question["card"]["target_form"] == "ruokaa")
        self.assertEqual(food_form["prompt"], "____ on, ____!")
        self.assertEqual(food_form["english_translations"], ["There is food.", "Food exists."])
        self.assertEqual(len(food_form["options"]), 3)
        self.assertEqual(sum(option["id"] == food_form["correct_option_id"] for option in food_form["options"]), 1)
        self.assertFalse(any(question["card"]["type"] == "word_form" and question["card"]["base_word"] == "talo" for question in questions))


class HierarchicalBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "sentences").mkdir()
        (self.root / "dictionary.txt").write_text("auto - car\n", encoding="utf-8")
        (self.root / "word-forms.txt").write_text(
            "autossa - autossani / autossasi\nauto - autossa\n", encoding="utf-8"
        )
        (self.root / "sentences" / "lesson.txt").write_text(
            "Auto on uusi. - The car is new.\nAutossa istun. - I sit in the car.\n"
            "Autossani istun. - I sit in my car.\nAutossasi istut. - You sit in your car.\n",
            encoding="utf-8",
        )
        run_import(self.root)
        self.content = self.root / "data" / "content.sqlite"
        self.progress = self.root / "data" / "progress.sqlite"
        initialize_progress_database(self.progress)
        self.vocabulary = CardReference(type="vocabulary", base_word="auto")
        self.parent_form = CardReference(type="word_form", base_word="auto", target_form="autossa")
        for attempt_id in ("vocabulary-1", "vocabulary-2", "vocabulary-3"):
            record_answer(self.progress, self.vocabulary, attempt_id, True, cooldown_minutes=0)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_nested_forms_unlock_after_immediate_parent_and_use_branch_options(self) -> None:
        before_parent_mastery = build_batch(self.content, self.progress, 20, random.Random(4))
        self.assertFalse(any(question["card"]["target_form"] == "autossani" for question in before_parent_mastery))

        for attempt_id in ("parent-1", "parent-2", "parent-3"):
            record_answer(self.progress, self.parent_form, attempt_id, True, cooldown_minutes=0)
        after_parent_mastery = build_batch(self.content, self.progress, 20, random.Random(4))
        nested = next(question for question in after_parent_mastery if question["card"]["target_form"] == "autossani")
        option_texts = {option["text"] for option in nested["options"]}
        self.assertEqual(option_texts, {"autossa", "autossani", "autossasi"})

        reset_card(self.progress, self.parent_form)
        after_reset = build_batch(self.content, self.progress, 20, random.Random(4))
        self.assertFalse(any(question["card"]["target_form"] == "autossani" for question in after_reset))


if __name__ == "__main__":
    unittest.main()
