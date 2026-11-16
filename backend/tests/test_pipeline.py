from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.pipeline import run_import


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "sentences").mkdir()

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
        self.assertEqual(len(report.skipped_lines), 4)

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
        database.close()
        self.assertEqual(translations, [("I eat food.",), ("I am eating food.",)])
        self.assertIn("Imported vocabulary: 2", (self.root / "data" / "import-report.txt").read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
