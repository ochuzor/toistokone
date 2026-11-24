from __future__ import annotations

import tempfile
import unittest
import hashlib
import sqlite3
from pathlib import Path

from backend.app.content_health import analyze_content_health, get_content_health
from backend.app.config import Settings
from backend.app.db import initialize_progress_database
from backend.app.main import app, content_health
from backend.pipeline import run_import
from backend.tests.kaikki_fixture import write_kaikki


class ContentHealthTests(unittest.TestCase):
    def test_analysis_counts_exact_support_and_ignores_untracked_tokens(self) -> None:
        health = analyze_content_health(
            ["talo", "New York", "ilman"],
            [("talo", "talossa", "Inessiivi (missä?)"), ("talo", "talosta", "Elatiivi (mistä?)")],
            {
                "Talossa asun.": ["I live in the house."],
                "Talo on suuri.": ["The house is large."],
                "New York on suuri.": ["New York is large."],
                "Irrallinen lause.": ["An unrelated sentence."],
            },
        )

        self.assertEqual([item.word for item in health.missing_profiles], ["ilman", "New York"])
        self.assertEqual([item.word for item in health.base_without_sentences], ["ilman"])
        self.assertEqual([(item.form, item.sentence_count) for item in health.under_supported_forms], [("talossa", 1), ("talosta", 0)])
        self.assertEqual([item.finnish for item in health.untracked_sentences], ["Irrallinen lause."])

    def test_prioritizes_coverage_and_untracked_sentences(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            progress_path = Path(directory) / "progress.sqlite"
            initialize_progress_database(progress_path)
            with sqlite3.connect(progress_path) as connection:
                connection.execute("INSERT INTO focus_vocabulary (base_word, requested_at) VALUES ('focus', '2026-01-01T00:00:00+00:00')")
                connection.execute(
                    """INSERT INTO card_progress (card_type, base_word, target_form, score, last_practiced_at)
                       VALUES ('vocabulary', 'recent', '', 1, '2026-02-01T00:00:00+00:00')"""
                )

            health = analyze_content_health(
                ["rare", "recent", "focus", "common", "unranked"],
                [("common", "commonform", "Test form")],
                {
                    "yleinen.": ["Common."],
                    "yleinen pieni.": ["Common small."],
                    "yleinen tuntematon.": ["Common unknown."],
                },
                progress_path=progress_path,
                frequency_ranks={"common": 1, "commonform": 2, "recent": 5, "rare": 50, "yleinen": 3, "pieni": 4},
            )

        self.assertEqual([item.word for item in health.missing_profiles], ["focus", "recent", "rare", "unranked"])
        self.assertEqual([item.priority_reason for item in health.missing_profiles[:3]], ["Focus word", "Practised recently", "Frequency rank #50"])
        self.assertEqual(health.under_supported_forms[0].priority_reason, "Frequency rank #2")
        self.assertEqual(
            [item.finnish for item in health.untracked_sentences],
            ["yleinen.", "yleinen pieni.", "yleinen tuntematon."],
        )


class ContentHealthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.root = root
        (root / "sentences").mkdir()
        (root / "frequency").mkdir()
        write_kaikki(root)
        (root / "frequency" / "fi_50k.txt").write_text("talo 10\nirrallinen 5\n", encoding="utf-8")
        (root / "dictionary.txt").write_text("talo - house\n", encoding="utf-8")
        (root / "sentences" / "lesson.txt").write_text("Talossa asun. - I live in the house.\nIrrallinen lause. - An unrelated sentence.\n", encoding="utf-8")
        initialize_progress_database(root / "data" / "progress.sqlite")
        with sqlite3.connect(root / "data" / "progress.sqlite") as connection:
            connection.execute("INSERT INTO focus_vocabulary (base_word, requested_at) VALUES ('talo', '2026-01-01T00:00:00+00:00')")
        self.progress_hash_before_import = hashlib.sha256((root / "data" / "progress.sqlite").read_bytes()).hexdigest()
        run_import(root)
        app.state.settings = Settings(20, 15, root / "data" / "content.sqlite", root / "data" / "progress.sqlite")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_api_returns_summary_and_paginated_form_findings(self) -> None:
        response = content_health("under_supported_forms", 0, 1)

        self.assertEqual(response.category, "under_supported_forms")
        self.assertGreater(response.summary.under_supported_forms, 0)
        self.assertEqual(len(response.findings), 1)
        self.assertEqual(response.total, len(get_content_health(app.state.settings.content_db_path, app.state.settings.progress_db_path).under_supported_forms))
        self.assertEqual(response.findings[0].base_word, "talo")
        self.assertEqual(response.findings[0].priority_reason, "Focus word")

    def test_import_report_renders_complete_content_health_sections(self) -> None:
        report = (self.root / "data" / "import-report.txt").read_text(encoding="utf-8")

        self.assertIn("Content health:", report)
        self.assertIn("Words without usable Kaikki profiles:", report)
        self.assertIn("Base words without supporting sentences:", report)
        self.assertIn("Form cards with fewer than two supporting sentences:", report)
        self.assertIn("Sentences without tracked vocabulary or forms:", report)
        self.assertIn("Focus word", report)
        self.assertEqual(
            hashlib.sha256((self.root / "data" / "progress.sqlite").read_bytes()).hexdigest(),
            self.progress_hash_before_import,
        )
