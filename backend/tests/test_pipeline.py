from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.pipeline import ImportReport, ImportValidationError, main, run_import


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "sentences").mkdir()
        (self.root / "frequency").mkdir()
        (self.root / "frequency" / "fi_50k.txt").write_text("talo 100\nruoka 90\nauto 80\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_sources(self, dictionary: str, forms: str, sentences: dict[str, str]) -> None:
        (self.root / "dictionary.txt").write_text(dictionary, encoding="utf-8")
        (self.root / "word-forms.txt").write_text(forms, encoding="utf-8")
        for name, contents in sentences.items():
            (self.root / "sentences" / name).write_text(contents, encoding="utf-8")

    def test_import_builds_schema_deduplicates_content_and_inserts_base_forms(self) -> None:
        self.write_sources(
            "# comment\ntalo - house / home\nruoka - food / meal\ntalo - building\ninvalid\n",
            "ruoka - ruokaa / ruoasta / ruoan\nmissing - nope\nruoka - ruokaa\n",
            {
                "a.txt": "Minä syön ruokaa. - I eat food. / I am eating food.\n",
                "b.txt": "Minä syön ruokaa. - I am eating food. / I eat food.\nRuoka on hyvää. - The food is good.\n",
            },
        )

        report = run_import(self.root)

        self.assertEqual(report.vocabulary_count, 2)
        self.assertEqual(report.dictionary_file_count, 1)
        self.assertEqual(report.word_forms_file_count, 1)
        self.assertEqual(report.sentence_file_count, 2)
        self.assertEqual(report.form_count, 5)  # talo plus ruoka and its three additional forms
        self.assertEqual(report.sentence_count, 2)
        self.assertEqual(report.translation_count, 3)
        self.assertEqual(report.duplicate_vocabulary_count, 1)
        self.assertEqual(report.duplicate_form_count, 1)
        self.assertEqual(report.duplicate_sentence_count, 1)
        self.assertEqual(report.duplicate_translation_count, 2)
        self.assertEqual(len(report.skipped_lines), 3)
        self.assertEqual(report.missing_word_form_children, {"missing": ["nope"]})

        database = sqlite3.connect(self.root / "data" / "content.sqlite")
        self.assertEqual(database.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0], 2)
        self.assertEqual(database.execute("SELECT COUNT(*) FROM word_forms").fetchone()[0], 5)
        self.assertEqual(
            database.execute(
                "SELECT token_casefold FROM sentence_tokens WHERE token_casefold = ?", ("minä",)
            ).fetchall(),
            [("minä",)],
        )
        translations = database.execute(
            "SELECT english FROM sentence_translations JOIN sentences ON sentences.id = sentence_id "
            "WHERE finnish = ? ORDER BY ordinal",
            ("Minä syön ruokaa.",),
        ).fetchall()
        frequency_count = database.execute("SELECT COUNT(*) FROM frequency_words").fetchone()[0]
        database.close()
        self.assertEqual(translations, [("I eat food.",), ("I am eating food.",)])
        self.assertIn("Imported vocabulary: 2", (self.root / "data" / "import-report.txt").read_text(encoding="utf-8"))
        self.assertEqual(frequency_count, 3)

    def test_missing_or_invalid_frequency_file_is_fatal_and_preserves_databases(self) -> None:
        self.write_sources("talo - house\n", "", {"lesson.txt": "Talo on suuri. - The house is big.\n"})
        data_dir = self.root / "data"
        data_dir.mkdir()
        content_path = data_dir / "content.sqlite"
        progress_path = data_dir / "progress.sqlite"
        content_path.write_bytes(b"existing-content")
        progress_path.write_bytes(b"persistent-progress")
        frequency_path = self.root / "frequency" / "fi_50k.txt"

        for contents, expected_error in [(None, "missing required frequency file"), ("talo no\n", "invalid frequency count"), ("talo 1\nTALO 2\n", "duplicate frequency word")]:
            with self.subTest(contents=contents):
                if contents is None:
                    frequency_path.unlink(missing_ok=True)
                else:
                    frequency_path.write_text(contents, encoding="utf-8")
                with self.assertRaises(ImportValidationError) as raised:
                    run_import(self.root)
                self.assertIn(expected_error, raised.exception.report.fatal_errors[0])
                self.assertEqual(content_path.read_bytes(), b"existing-content")
                self.assertEqual(progress_path.read_bytes(), b"persistent-progress")

    def test_dry_run_preserves_content_and_progress_databases(self) -> None:
        self.write_sources("talo - house\n", "", {"lesson.txt": "Talo on suuri. - The house is big.\n"})
        data_dir = self.root / "data"
        data_dir.mkdir()
        content_path = data_dir / "content.sqlite"
        progress_path = data_dir / "progress.sqlite"
        content_path.write_bytes(b"existing-content")
        progress_path.write_bytes(b"persistent-progress")

        run_import(self.root, dry_run=True)

        self.assertEqual(content_path.read_bytes(), b"existing-content")
        self.assertEqual(progress_path.read_bytes(), b"persistent-progress")
        self.assertTrue((data_dir / "import-report.txt").exists())

    def test_normal_import_replaces_content_without_touching_progress(self) -> None:
        self.write_sources("talo - house\n", "", {"lesson.txt": "Talo on suuri. - The house is big.\n"})
        data_dir = self.root / "data"
        data_dir.mkdir()
        progress_path = data_dir / "progress.sqlite"
        progress_path.write_bytes(b"persistent-progress")

        run_import(self.root)

        self.assertTrue((data_dir / "content.sqlite").exists())
        self.assertEqual(progress_path.read_bytes(), b"persistent-progress")

    def test_batched_sentence_import_preserves_translations_and_token_mappings(self) -> None:
        self.write_sources(
            "talo - house\nruoka - food\n",
            "",
            {
                "lesson.txt": (
                    "Talo on suuri. - The house is big. / A large house.\n"
                    "Ruoka on hyvää. - The food is good.\n"
                )
            },
        )

        run_import(self.root)

        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            translations = database.execute(
                """SELECT sentences.finnish, sentence_translations.english, sentence_translations.ordinal
                   FROM sentence_translations JOIN sentences ON sentences.id = sentence_id
                   ORDER BY sentences.id, sentence_translations.ordinal"""
            ).fetchall()
            token_rows = database.execute(
                """SELECT sentences.finnish, sentence_tokens.token_casefold
                   FROM sentence_tokens JOIN sentences ON sentences.id = sentence_id
                   ORDER BY sentences.id, sentence_tokens.token_casefold"""
            ).fetchall()

        self.assertEqual(
            translations,
            [
                ("Talo on suuri.", "The house is big.", 0),
                ("Talo on suuri.", "A large house.", 1),
                ("Ruoka on hyvää.", "The food is good.", 0),
            ],
        )
        self.assertEqual(
            token_rows,
            [
                ("Talo on suuri.", "on"),
                ("Talo on suuri.", "suuri"),
                ("Talo on suuri.", "talo"),
                ("Ruoka on hyvää.", "hyvää"),
                ("Ruoka on hyvää.", "on"),
                ("Ruoka on hyvää.", "ruoka"),
            ],
        )

    def test_import_builds_nested_form_tree_in_any_declaration_order(self) -> None:
        self.write_sources(
            "auto - car\n",
            "autossa - autossani / autossasi\nauto - autossa\n",
            {"lesson.txt": "Autossani olen. - I am in my car.\n"},
        )

        run_import(self.root)

        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            rows = database.execute(
                """SELECT form, parent_form FROM word_forms
                   JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id
                   WHERE vocabulary.finnish = 'auto' ORDER BY word_forms.id"""
            ).fetchall()
        self.assertEqual(rows, [("auto", None), ("autossa", "auto"), ("autossani", "autossa"), ("autossasi", "autossa")])

    def test_report_lists_missing_word_form_roots_alphabetically(self) -> None:
        self.write_sources(
            "auto - car\n",
            "zeta - child-z\nalfa - child-a\nzeta - child-z-again\nauto - autossa\n",
            {"lesson.txt": "Auto on uusi. - The car is new.\n"},
        )

        report = run_import(self.root)

        self.assertEqual(report.missing_word_form_children, {"alfa": ["child-a"], "zeta": ["child-z", "child-z-again"]})
        rendered = (self.root / "data" / "import-report.txt").read_text(encoding="utf-8")
        self.assertIn("Missing word-form roots:\n- alfa:\n  - child-a\n- zeta:\n  - child-z\n  - child-z-again", rendered)

        dry_run = run_import(self.root, dry_run=True)
        self.assertEqual(dry_run.missing_word_form_children, {"alfa": ["child-a"], "zeta": ["child-z", "child-z-again"]})

    def test_cycle_is_fatal_and_preserves_existing_databases(self) -> None:
        self.write_sources(
            "auto - car\n",
            "autossa - autossani\nautossani - autossa\n",
            {"lesson.txt": "Auto on uusi. - The car is new.\n"},
        )
        data_dir = self.root / "data"
        data_dir.mkdir()
        content_path = data_dir / "content.sqlite"
        progress_path = data_dir / "progress.sqlite"
        content_path.write_bytes(b"existing-content")
        progress_path.write_bytes(b"persistent-progress")

        with self.assertRaises(ImportValidationError) as raised:
            run_import(self.root)

        self.assertIn("word-form cycle: autossa -> autossani -> autossa", raised.exception.report.fatal_errors[0])
        self.assertEqual(content_path.read_bytes(), b"existing-content")
        self.assertEqual(progress_path.read_bytes(), b"persistent-progress")
        report = (data_dir / "import-report.txt").read_text(encoding="utf-8")
        self.assertIn("Errors:", report)

        with self.assertRaises(ImportValidationError):
            run_import(self.root, dry_run=True)
        self.assertEqual(content_path.read_bytes(), b"existing-content")
        self.assertEqual(progress_path.read_bytes(), b"persistent-progress")

    def test_main_exits_non_zero_for_fatal_cycle(self) -> None:
        report = ImportReport(fatal_errors=["word-forms.txt: line 1: word-form cycle: a -> a"])
        with patch("backend.pipeline.run_import", side_effect=ImportValidationError(report)):
            with patch("sys.argv", ["pipeline"]):
                with self.assertRaises(SystemExit) as raised:
                    main()
        self.assertEqual(raised.exception.code, 1)

    def test_report_groups_forms_with_fewer_than_two_supporting_sentences(self) -> None:
        self.write_sources(
            "auto - car\ntalo - house\n",
            "autossa - autossani\nauto - autossa\nmissing - orphan\n",
            {
                "lesson.txt": (
                    "AUTO auto. - The car is new. / A new car.\n"
                    "Autossa istun. - I sit in the car.\n"
                    "autossa odotan. - I wait in the car.\n"
                    "autossaikaa ei lasketa. - This substring does not count.\n"
                )
            },
        )

        report = run_import(self.root)

        self.assertEqual(report.insufficient_sentence_support, {"auto": [("auto", 1), ("autossani", 0)], "talo": [("talo", 0)]})
        rendered = (self.root / "data" / "import-report.txt").read_text(encoding="utf-8")
        self.assertIn("Insufficient sentence support:\n- auto:\n  - auto (1)\n  - autossani (0)\n- talo:\n  - talo (0)", rendered)

        dry_run = run_import(self.root, dry_run=True)
        self.assertEqual(dry_run.insufficient_sentence_support, report.insufficient_sentence_support)


if __name__ == "__main__":
    unittest.main()
