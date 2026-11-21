from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.app.config import Settings
from backend.app.db import initialize_progress_database
from backend.app.main import answer, app, quiz_batch, recommendations, reset, stats
from backend.app.models import AnswerRequest, ResetRequest
from backend.pipeline import run_import
from backend.tests.kaikki_fixture import write_kaikki


class ProgressApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
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

        self.assertEqual(stats().overall.model_dump(), {"total": 7, "mastered": 0, "mastery_percent": 0.0})
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

    def test_quiz_batch_route_returns_current_content_without_writing_progress(self) -> None:
        batch = quiz_batch()
        self.assertEqual(len(batch.questions), 1)
        self.assertEqual(batch.questions[0].card.base_word, "talo")

    def test_recommendations_route_returns_contextual_words(self) -> None:
        response = recommendations()
        self.assertEqual(response.recommendations[0].word, "suuri")
        self.assertEqual(response.recommendations[0].examples[0].english_translations, ["The house is big."])


if __name__ == "__main__":
    unittest.main()
