from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.db import get_stats, initialize_progress_database, record_answer, reset_card
from backend.app.models import CardReference
from backend.pipeline import run_import
from backend.tests.kaikki_fixture import write_kaikki


class ProgressDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "sentences").mkdir()
        (self.root / "frequency").mkdir()
        write_kaikki(self.root)
        (self.root / "frequency" / "fi_50k.txt").write_text("talo 100\nruoka 90\n", encoding="utf-8")
        (self.root / "dictionary.txt").write_text("talo - house\nruoka - food\n", encoding="utf-8")
        (self.root / "sentences" / "lesson.txt").write_text("Ruokaa on. - There is food.\n", encoding="utf-8")
        run_import(self.root)
        self.content_path = self.root / "data" / "content.sqlite"
        self.progress_path = self.root / "data" / "progress.sqlite"
        initialize_progress_database(self.progress_path)
        self.vocabulary = CardReference(type="vocabulary", base_word="talo")
        self.form = CardReference(type="word_form", base_word="ruoka", target_form="nominal:partitive")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_score_transitions_and_mastery_are_exact(self) -> None:
        transitions = []
        for attempt_id, correct in [("a", False), ("b", True), ("c", True), ("d", False), ("e", True), ("f", False)]:
            transitions.append(record_answer(self.progress_path, self.vocabulary, attempt_id, correct, cooldown_minutes=0)["score_after"])
        self.assertEqual(transitions, [0, 1, 2, 1, 2, 1])

        for attempt_id in ("g", "h"):
            record_answer(self.progress_path, self.vocabulary, attempt_id, True, cooldown_minutes=0)
        mastered = record_answer(self.progress_path, self.vocabulary, "i", False, cooldown_minutes=0)
        self.assertEqual(mastered, {"correct": False, "score_before": 3, "score_after": 3})

    def test_idempotency_preserves_score_history_and_timestamp(self) -> None:
        first = record_answer(self.progress_path, self.vocabulary, "same-attempt", True, cooldown_minutes=0)
        repeated = record_answer(self.progress_path, self.vocabulary, "same-attempt", False, cooldown_minutes=0)
        self.assertEqual(first, repeated)
        with sqlite3.connect(self.progress_path) as connection:
            self.assertEqual(connection.execute("SELECT attempt_count, correct_count FROM card_progress").fetchone(), (1, 1))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM practice_attempts").fetchone()[0], 1)
            self.assertIsNotNone(connection.execute("SELECT last_practiced_at FROM card_progress").fetchone()[0])

    def test_reset_retains_history_and_stats_exclude_orphaned_progress(self) -> None:
        for attempt_id in ("one", "two", "three"):
            record_answer(self.progress_path, self.vocabulary, attempt_id, True, cooldown_minutes=0)
        for attempt_id in ("four", "five", "six"):
            record_answer(self.progress_path, self.form, attempt_id, True, cooldown_minutes=0)
        self.assertEqual(get_stats(self.content_path, self.progress_path)["overall"], {"total": 14, "mastered": 2, "mastery_percent": 14.29})

        reset_card(self.progress_path, self.vocabulary)
        with sqlite3.connect(self.progress_path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM practice_attempts").fetchone()[0], 6)
        self.assertEqual(get_stats(self.content_path, self.progress_path)["overall"]["mastered"], 1)

        (self.root / "dictionary.txt").write_text("ruoka - food\n", encoding="utf-8")
        run_import(self.root)
        self.assertEqual(get_stats(self.content_path, self.progress_path)["overall"]["mastered"], 1)

    def test_cooldown_blocks_score_changes_but_records_attempts(self) -> None:
        started_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        first = record_answer(
            self.progress_path, self.vocabulary, "first", True, cooldown_minutes=15, now=started_at
        )
        blocked_correct = record_answer(
            self.progress_path, self.vocabulary, "blocked-correct", True, cooldown_minutes=15,
            now=started_at + timedelta(minutes=14, seconds=59),
        )
        blocked_incorrect = record_answer(
            self.progress_path, self.vocabulary, "blocked-incorrect", False, cooldown_minutes=15,
            now=started_at + timedelta(minutes=14, seconds=59),
        )
        eligible = record_answer(
            self.progress_path, self.vocabulary, "eligible", True, cooldown_minutes=15,
            now=started_at + timedelta(minutes=15),
        )

        self.assertEqual(first["score_after"], 1)
        self.assertEqual(blocked_correct["score_after"], 1)
        self.assertEqual(blocked_incorrect["score_after"], 1)
        self.assertEqual(eligible["score_after"], 2)
        with sqlite3.connect(self.progress_path) as connection:
            row = connection.execute(
                "SELECT last_score_increased_at, last_practiced_at, attempt_count FROM card_progress"
            ).fetchone()
        eligible_at = (started_at + timedelta(minutes=15)).isoformat()
        self.assertEqual(row, (eligible_at, eligible_at, 4))
        self.assertEqual(reset_card(self.progress_path, self.vocabulary), 0)
        with sqlite3.connect(self.progress_path) as connection:
            self.assertEqual(connection.execute("SELECT score FROM card_progress").fetchone()[0], 0)

    def test_existing_progress_database_is_migrated_in_place(self) -> None:
        with sqlite3.connect(self.progress_path) as connection:
            connection.execute("DROP TABLE card_progress")
            connection.execute(
                """CREATE TABLE card_progress (
                   card_type TEXT NOT NULL, base_word TEXT NOT NULL, target_form TEXT NOT NULL DEFAULT '',
                   score INTEGER NOT NULL DEFAULT 0, last_practiced_at TEXT,
                   attempt_count INTEGER NOT NULL DEFAULT 0, correct_count INTEGER NOT NULL DEFAULT 0,
                   PRIMARY KEY (card_type, base_word, target_form))"""
            )
            connection.execute(
                "INSERT INTO card_progress VALUES ('vocabulary', 'talo', '', 2, '2026-01-01T00:00:00+00:00', 3, 2)"
            )
        initialize_progress_database(self.progress_path)
        with sqlite3.connect(self.progress_path) as connection:
            columns = {column[1] for column in connection.execute("PRAGMA table_info(card_progress)")}
            progress = connection.execute("SELECT score, attempt_count, correct_count FROM card_progress").fetchone()
        self.assertIn("last_score_increased_at", columns)
        self.assertEqual(progress, (2, 3, 2))

    def test_daily_activity_uses_local_dates_and_carries_a_streak_through_today(self) -> None:
        first_day = datetime(2026, 1, 13, 12, 0, tzinfo=timezone.utc)
        second_day = datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc)
        local_today = datetime(2026, 1, 14, 22, 30, tzinfo=timezone.utc)
        for attempt_id, answered_at in (("first", first_day), ("second", second_day), ("third", local_today)):
            record_answer(self.progress_path, self.vocabulary, attempt_id, True, cooldown_minutes=0, now=answered_at)

        stats = get_stats(
            self.content_path,
            self.progress_path,
            "Europe/Helsinki",
            now=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )

        activity = stats["activity"]
        self.assertEqual(activity["today"], {
            "date": "2026-01-15", "attempts": 1, "correct": 1, "accuracy_percent": 100.0,
            "unique_cards": 1, "score_increases": 1, "newly_mastered": 1,
        })
        self.assertEqual(len(activity["days"]), 14)
        self.assertEqual(activity["days"][0]["attempts"], 0)
        self.assertEqual(activity["streak_days"], 3)

        carried = get_stats(
            self.content_path,
            self.progress_path,
            "Europe/Helsinki",
            now=datetime(2026, 1, 16, 10, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(carried["activity"]["streak_days"], 3)

    def test_daily_activity_rejects_unknown_timezones(self) -> None:
        with self.assertRaises(ValueError):
            get_stats(self.content_path, self.progress_path, "Not/A-Timezone")

if __name__ == "__main__":
    unittest.main()
