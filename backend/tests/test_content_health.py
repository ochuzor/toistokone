from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.content_health import analyze_content_health, get_content_health
from backend.app.config import Settings
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

        self.assertEqual(health.missing_profiles, ["ilman", "New York"])
        self.assertEqual(health.base_without_sentences, ["ilman"])
        self.assertEqual([(item.form, item.sentence_count) for item in health.under_supported_forms], [("talossa", 1), ("talosta", 0)])
        self.assertEqual([item.finnish for item in health.untracked_sentences], ["Irrallinen lause."])


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
        run_import(root)
        app.state.settings = Settings(20, 15, root / "data" / "content.sqlite", root / "data" / "progress.sqlite")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_api_returns_summary_and_paginated_form_findings(self) -> None:
        response = content_health("under_supported_forms", 0, 1)

        self.assertEqual(response.category, "under_supported_forms")
        self.assertGreater(response.summary.under_supported_forms, 0)
        self.assertEqual(len(response.findings), 1)
        self.assertEqual(response.total, len(get_content_health(app.state.settings.content_db_path).under_supported_forms))
        self.assertEqual(response.findings[0].base_word, "talo")

    def test_import_report_renders_complete_content_health_sections(self) -> None:
        report = (self.root / "data" / "import-report.txt").read_text(encoding="utf-8")

        self.assertIn("Content health:", report)
        self.assertIn("Base words without supporting sentences:", report)
        self.assertIn("Form cards with fewer than two supporting sentences:", report)
        self.assertIn("Sentences without tracked vocabulary or forms:", report)
