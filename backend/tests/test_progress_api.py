from __future__ import annotations

import tempfile
import unittest
import json
import sqlite3
from pathlib import Path

from fastapi import HTTPException

from backend.app.config import Settings
from backend.app.db import initialize_progress_database, list_vocabulary
from backend.app.main import acknowledge_grammar_guide, active_learning_set, add_focus_word, answer, app, content_version, delete_focus_word, focus_words, grammar_guide, learning_path_detail, learning_paths, learning_set_detail, learning_sets, quiz_batch, recommendations, reset, sentence_break, stats, vocabulary
from backend.app.models import ActiveLearningSetRequest, AnswerRequest, FocusWordRequest, ResetRequest
from backend.pipeline import run_import
from backend.tests.kaikki_fixture import write_kaikki


class ProgressApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.root = root
        (root / "sentences").mkdir()
        (root / "frequency").mkdir()
        write_kaikki(root)
        (root / "frequency" / "fi_50k.txt").write_text("suuri 100\ntalo 90\n", encoding="utf-8")
        (root / "dictionary.txt").write_text("talo - house\n", encoding="utf-8")
        (root / "sentences" / "lesson.txt").write_text("Talo on suuri. - The house is big.\n", encoding="utf-8")
        run_import(root)
        self.settings = Settings(
            quiz_batch_size=20,
            card_score_cooldown_minutes=15,
            content_db_path=root / "data" / "content.sqlite",
            progress_db_path=root / "data" / "progress.sqlite",
        )
        initialize_progress_database(self.settings.progress_db_path)
        app.state.settings = self.settings

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_answer_reset_and_stats_routes(self) -> None:
        payload = {
            "attempt_id": "attempt-1",
            "card": {"type": "vocabulary", "base_word": "talo", "target_form": ""},
            "selected_option_id": "a",
            "correct_option_id": "a",
        }
        result = answer(AnswerRequest(**payload))
        self.assertEqual(result.model_dump(), {"correct": True, "score_before": 0, "score_after": 1, "mastered": False})

        cooldown_attempt = answer(AnswerRequest(**{**payload, "attempt_id": "attempt-2"}))
        self.assertEqual(cooldown_attempt.model_dump(), {"correct": True, "score_before": 1, "score_after": 1, "mastered": False})

        retry = answer(AnswerRequest(**{**payload, "selected_option_id": "wrong"}))
        self.assertEqual(retry.model_dump(), result.model_dump())

        response = stats("Europe/Helsinki")
        self.assertEqual(response.overall.model_dump(), {"total": 11, "mastered": 0, "mastery_percent": 0.0})
        self.assertEqual(len(response.activity.days), 14)
        self.assertEqual(reset(ResetRequest(card=payload["card"])).model_dump(), {"score": 0})

    def test_rejects_card_absent_from_current_content(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            answer(
                AnswerRequest(
                    attempt_id="missing-card",
                    card={"type": "word_form", "base_word": "talo", "target_form": "missing-slot"},
                    selected_option_id="a",
                    correct_option_id="a",
                )
            )
        self.assertEqual(raised.exception.status_code, 404)

    def test_grammar_guide_is_seen_without_changing_card_progress(self) -> None:
        directory = self.root / "grammar-guides"
        directory.mkdir()
        (directory / "allative.md").write_text(
            "---\nid: nominal-allative\nform: nominal:allative\nsummary: Direction or a recipient.\n"
            "example: Kirja pöydälle. | A book onto the table.\n"
            "example: Anna se opettajalle. | Give it to the teacher.\n---\n\n# Allatiivi\n\nMore detail.\n",
            encoding="utf-8",
        )
        run_import(self.root)
        before = grammar_guide("nominal-allative")
        self.assertFalse(before.seen)
        self.assertTrue(acknowledge_grammar_guide("nominal-allative").seen)
        self.assertTrue(grammar_guide("nominal-allative").seen)
        with sqlite3.connect(self.settings.progress_db_path) as database:
            self.assertEqual(database.execute("SELECT COUNT(*) FROM card_progress").fetchone()[0], 0)

    def test_stats_rejects_unknown_timezone(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            stats("Not/A-Timezone")
        self.assertEqual(raised.exception.status_code, 422)

    def test_quiz_batch_route_returns_current_content_without_writing_progress(self) -> None:
        batch = quiz_batch()
        self.assertEqual(len(batch.questions), 1)
        self.assertEqual(batch.questions[0].card.base_word, "talo")

    def test_sentence_break_route_returns_no_sentences_without_mastered_cards(self) -> None:
        self.assertEqual(sentence_break().sentences, [])

    def test_content_version_route_returns_pipeline_revision(self) -> None:
        response = content_version()
        self.assertRegex(response.revision, r"^[0-9a-f]{32}$")

    def test_learning_set_routes_list_select_and_clear_a_set(self) -> None:
        words = ["talo", *[f"word-{number}" for number in range(1, 10)]]
        (self.root / "dictionary.txt").write_text("".join(f"{word} - meaning\n" for word in words), encoding="utf-8")
        directory = self.root / "learning-sets"
        directory.mkdir()
        (directory / "home.md").write_text("---\nid: home\n---\n# Home life\n" + "".join(f"- {word}\n" for word in words), encoding="utf-8")
        run_import(self.root)

        initial = learning_sets().learning_sets
        self.assertEqual(initial[0].key, "home")
        self.assertFalse(initial[0].active)
        self.assertEqual(initial[0].words.model_dump(), {"total": 10, "mastered": 0})

        self.assertEqual(active_learning_set(ActiveLearningSetRequest(set_key="home")).set_key, "home")
        self.assertTrue(learning_sets().learning_sets[0].active)
        self.assertIsNone(active_learning_set(ActiveLearningSetRequest(set_key=None)).set_key)
        self.assertFalse(learning_sets().learning_sets[0].active)

        with self.assertRaises(HTTPException) as raised:
            active_learning_set(ActiveLearningSetRequest(set_key="missing"))
        self.assertEqual(raised.exception.status_code, 404)

    def test_learning_set_detail_returns_member_progress_in_set_order(self) -> None:
        words = ["talo", *[f"word-{number}" for number in range(1, 10)]]
        (self.root / "dictionary.txt").write_text(
            "talo - house\n" + "".join(f"{word} - meaning\n" for word in words[1:]), encoding="utf-8"
        )
        directory = self.root / "learning-sets"
        directory.mkdir()
        (directory / "home.md").write_text("---\nid: home\n---\n# Home life\n" + "".join(f"- {word}\n" for word in words), encoding="utf-8")
        run_import(self.root)
        with sqlite3.connect(self.settings.progress_db_path) as connection:
            connection.execute(
                "INSERT INTO card_progress (card_type, base_word, target_form, score) VALUES ('vocabulary', 'talo', '', 2)"
            )
            connection.execute(
                "INSERT INTO card_progress (card_type, base_word, target_form, score) VALUES ('word_form', 'talo', 'nominal:genitive', 3)"
            )

        detail = learning_set_detail("home")

        self.assertEqual(detail.title, "Home life")
        self.assertEqual([word.finnish for word in detail.words], words)
        self.assertEqual(detail.words[0].model_dump(), {
            "finnish": "talo", "meanings": ["house"], "score": 2,
            "word_forms": {"total": 10, "mastered": 1},
        })
        self.assertFalse(detail.active)
        active_learning_set(ActiveLearningSetRequest(set_key="home"))
        self.assertTrue(learning_set_detail("home").active)
        with self.assertRaises(HTTPException) as raised:
            learning_set_detail("missing")
        self.assertEqual(raised.exception.status_code, 404)

    def test_learning_set_detail_treats_forms_only_word_as_base_mastered(self) -> None:
        words = ["Tampere", *[f"word-{number}" for number in range(1, 10)]]
        (self.root / "dictionary.txt").write_text(
            "Tampere - Tampere\n" + "".join(f"{word} - meaning\n" for word in words[1:]), encoding="utf-8"
        )
        directory = self.root / "learning-sets"
        directory.mkdir()
        (directory / "places.md").write_text("---\nid: places\n---\n# Places\n" + "".join(f"- {word}\n" for word in words), encoding="utf-8")
        run_import(self.root)

        detail = learning_set_detail("places")

        self.assertEqual(detail.words[0].finnish, "Tampere")
        self.assertEqual(detail.words[0].score, 3)

    def test_learning_path_unlocks_at_score_two_thresholds_and_relocks_after_regression(self) -> None:
        first_words = ["talo", *[f"first-{number}" for number in range(1, 10)]]
        second_words = ["ruoka", *[f"second-{number}" for number in range(1, 10)]]
        (self.root / "dictionary.txt").write_text(
            "talo - house\nruoka - food\n" + "".join(f"{word} - meaning\n" for word in [*first_words[1:], *second_words[1:]]),
            encoding="utf-8",
        )
        sets = self.root / "learning-sets"
        sets.mkdir()
        for key, title, words in (("first", "First set", first_words), ("second", "Second set", second_words)):
            (sets / f"{key}.md").write_text(
                f"---\nid: {key}\n---\n# {title}\n" + "".join(f"- {word}\n" for word in words), encoding="utf-8"
            )
        paths = self.root / "learning-paths"
        paths.mkdir()
        (paths / "journey.md").write_text("---\nid: journey\n---\n# My journey\n- first\n- second\n", encoding="utf-8")
        run_import(self.root)

        initial = learning_path_detail("journey")
        self.assertEqual([step.state for step in initial.steps], ["available", "locked"])
        with sqlite3.connect(self.settings.content_db_path) as content:
            form_keys = [row[0] for row in content.execute("SELECT card_key FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id WHERE finnish = 'talo' ORDER BY card_key LIMIT 4")]
        with sqlite3.connect(self.settings.progress_db_path) as progress:
            progress.executemany(
                "INSERT INTO card_progress (card_type, base_word, target_form, score) VALUES ('vocabulary', ?, '', 2)",
                ((word,) for word in first_words[:7]),
            )
            progress.executemany(
                "INSERT INTO card_progress (card_type, base_word, target_form, score) VALUES ('word_form', 'talo', ?, 2)",
                ((form_key,) for form_key in form_keys),
            )

        progressed = learning_path_detail("journey")
        self.assertEqual([step.state for step in progressed.steps], ["completed", "available"])
        self.assertEqual(progressed.steps[0].vocabulary.model_dump(), {"total": 10, "qualified": 7, "percent": 70.0})
        self.assertEqual(progressed.steps[0].word_forms.model_dump(), {"total": 10, "qualified": 4, "percent": 40.0})
        self.assertFalse(progressed.completed)
        summary = learning_paths().learning_paths[0]
        self.assertEqual(summary.sets.model_dump(), {"total": 2, "mastered": 1})
        self.assertEqual(summary.next_step.key, "second")
        with sqlite3.connect(self.settings.progress_db_path) as progress:
            progress.execute("UPDATE card_progress SET score = 1 WHERE card_type = 'vocabulary' AND base_word = ?", (first_words[6],))

        regressed = learning_path_detail("journey")
        self.assertEqual([step.state for step in regressed.steps], ["available", "locked"])
        self.assertEqual(learning_paths().learning_paths[0].next_step.key, "first")
        with self.assertRaises(HTTPException) as raised:
            learning_path_detail("missing")
        self.assertEqual(raised.exception.status_code, 404)

    def test_recommendations_route_returns_contextual_words(self) -> None:
        response = recommendations()
        self.assertEqual(response.recommendations[0].word, "suuri")
        self.assertEqual(response.recommendations[0].examples[0].english_translations, ["The house is big."])

    def test_focus_word_routes_expose_and_remove_a_new_word_request(self) -> None:
        added = add_focus_word(FocusWordRequest(base_word="talo"))
        self.assertEqual(added.base_word, "talo")
        self.assertEqual(vocabulary("tal").vocabulary[0].focus_requested_at, added.requested_at)
        self.assertEqual(focus_words().vocabulary[0].finnish, "talo")
        self.assertEqual(delete_focus_word("talo").requested_at, added.requested_at)

        answer(AnswerRequest(
            attempt_id="practice-talo",
            card={"type": "vocabulary", "base_word": "talo", "target_form": ""},
            selected_option_id="correct",
            correct_option_id="correct",
        ))
        with self.assertRaises(HTTPException) as raised:
            add_focus_word(FocusWordRequest(base_word="talo"))
        self.assertEqual(raised.exception.status_code, 409)

    def test_forms_only_entries_are_hidden_from_vocabulary_and_focus_requests(self) -> None:
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        with path.open("a", encoding="utf-8") as source:
            source.write(json.dumps({
                "word": "Helsinki", "lang_code": "fi", "pos": "name",
                "forms": [
                    {"form": "Helsinki", "source": "declension", "tags": ["nominative", "singular"]},
                    {"form": "Helsingin", "source": "declension", "tags": ["genitive", "singular"]},
                    {"form": "Helsingissä", "source": "declension", "tags": ["inessive", "singular"]},
                ],
            }) + "\n")
        (self.root / "dictionary.txt").write_text("talo - house\nHelsinki - Helsinki\n", encoding="utf-8")
        run_import(self.root)

        self.assertEqual([entry["finnish"] for entry in list_vocabulary(self.settings.content_db_path, self.settings.progress_db_path)], ["talo"])
        with self.assertRaises(HTTPException) as raised:
            add_focus_word(FocusWordRequest(base_word="Helsinki"))
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
