from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.pipeline import run_import
from backend.tests.kaikki_fixture import write_kaikki
from backend.tatoeba_extract import extract_sentences, run_extraction


class TatoebaExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.frequency_path = self.root / "fi_50k.txt"
        self.source_path = self.root / "finn-eng.txt"
        write_kaikki(self.root)
        self.frequency_path.write_text("yleinen 100\nharvinainen 10\ntuttu 5\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_source(self, contents: str) -> None:
        self.source_path.write_text(contents, encoding="utf-8")

    def test_filters_by_length_and_frequency_then_consolidates_duplicates(self) -> None:
        self.write_source(
            "Yleinen tuttu. - Common familiar.\n"
            "Yleinen tuttu. - Familiar common.\n"
            "Yleinen tuttu. - Common familiar.\n"
            "Yleinen harvinainen poissa toinen. - Too many rare words.\n"
            "yleinen tuttu yleinen tuttu yleinen. - Too long.\n"
            "invalid source line\n"
        )

        sentences, report = extract_sentences(
            self.frequency_path,
            self.source_path,
            max_tokens=4,
            top_rank=2,
            max_rare_tokens=1,
        )

        self.assertEqual(sentences, {"Yleinen tuttu.": ["Common familiar.", "Familiar common."]})
        self.assertEqual(report.source_line_count, 6)
        self.assertEqual(report.accepted_pair_count, 3)
        self.assertEqual(report.duplicate_sentence_count, 2)
        self.assertEqual(report.duplicate_translation_count, 1)
        self.assertEqual(report.rejected_too_rare_count, 1)
        self.assertEqual(report.rejected_too_long_count, 1)
        self.assertEqual(report.malformed_line_count, 1)
        self.assertEqual(report.sentence_count, 1)
        self.assertEqual(report.translation_count, 2)

    def test_missing_frequency_forms_count_as_uncommon(self) -> None:
        self.write_source("Yleinen puuttuva. - Missing form.\n")

        sentences, report = extract_sentences(
            self.frequency_path,
            self.source_path,
            top_rank=2,
            max_rare_tokens=0,
        )

        self.assertEqual(sentences, {})
        self.assertEqual(report.rejected_too_rare_count, 1)

    def test_run_writes_import_ready_source_and_audit_report_without_overwriting(self) -> None:
        self.write_source("Yleinen tuttu. - Common familiar.\n")
        output_path = self.root / "sentences" / "tatoeba-filtered.txt"
        report_path = self.root / "audit" / "report.txt"

        report = run_extraction(
            self.frequency_path,
            self.source_path,
            output_path,
            report_path,
            top_rank=2,
        )

        self.assertEqual(report.sentence_count, 1)
        self.assertEqual(output_path.read_text(encoding="utf-8"), "Yleinen tuttu. - Common familiar.\n")
        rendered_report = report_path.read_text(encoding="utf-8")
        self.assertIn("Common-word rank limit: 2", rendered_report)
        self.assertIn("Output Finnish sentences: 1", rendered_report)
        (self.root / "dictionary.txt").write_text("yleinen - common\n", encoding="utf-8")
        (self.root / "frequency").mkdir()
        (self.root / "frequency" / "fi_50k.txt").write_text("yleinen 100\n", encoding="utf-8")
        imported = run_import(self.root)
        self.assertEqual(imported.sentence_count, 1)
        with self.assertRaises(FileExistsError):
            run_extraction(self.frequency_path, self.source_path, output_path, report_path, top_rank=2)


if __name__ == "__main__":
    unittest.main()
