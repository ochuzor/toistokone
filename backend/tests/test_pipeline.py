from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.pipeline import ImportReport, ImportValidationError, main, run_import
from backend.tests.kaikki_fixture import write_kaikki


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "sentences").mkdir()
        (self.root / "frequency").mkdir()
        (self.root / "frequency" / "fi_50k.txt").write_text("talo 100\nruoka 90\nauto 80\ntehdä 70\n", encoding="utf-8")
        write_kaikki(self.root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_sources(self, dictionary: str, sentences: dict[str, str] | None = None) -> None:
        (self.root / "dictionary.txt").write_text(dictionary, encoding="utf-8")
        for name, contents in (sentences or {}).items():
            (self.root / "sentences" / name).write_text(contents, encoding="utf-8")

    def test_import_generates_labelled_nominal_and_verb_forms(self) -> None:
        self.write_sources("talo - house\ntehdä - to do\nparticle - just\n", {"lesson.txt": "Talo on suuri. - The house is big.\n"})
        report = run_import(self.root)
        self.assertTrue(report.kaikki_index_rebuilt)
        self.assertTrue(report.recommendation_lemma_index_rebuilt)
        self.assertEqual(report.form_count, 12)
        self.assertEqual(report.missing_lexicon_profiles, ["particle"])
        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            talo = database.execute("SELECT card_key, form, profile, prompt_label FROM word_forms JOIN vocabulary ON vocabulary.id = vocabulary_id WHERE finnish = 'talo' ORDER BY card_key").fetchall()
            verb = database.execute("SELECT card_key, form, prompt_label FROM word_forms JOIN vocabulary ON vocabulary.id = vocabulary_id WHERE finnish = 'tehdä' ORDER BY card_key").fetchall()
        self.assertIn(("nominal:inessive", "talossa", "nominal", "Inessiivi (missä?)"), talo)
        self.assertNotIn(("nominal:nominative", "talo", "nominal", "Nominatiivi (mikä?)"), talo)
        self.assertIn(("nominal:nominative-plural", "talot", "nominal", "Nominatiivi, monikko (mitkä?)"), talo)
        self.assertIn(("verb:present-3sg", "tekee", "hän ____"), verb)
        second = run_import(self.root, dry_run=True)
        self.assertFalse(second.kaikki_index_rebuilt)
        self.assertFalse(second.recommendation_lemma_index_rebuilt)

    def test_normal_import_assigns_a_new_content_revision(self) -> None:
        self.write_sources("talo - house\n")
        run_import(self.root)
        content_path = self.root / "data" / "content.sqlite"
        with sqlite3.connect(content_path) as database:
            first_revision = database.execute(
                "SELECT value FROM content_metadata WHERE key = 'revision'"
            ).fetchone()[0]

        run_import(self.root)

        with sqlite3.connect(content_path) as database:
            second_revision = database.execute(
                "SELECT value FROM content_metadata WHERE key = 'revision'"
            ).fetchone()[0]
        self.assertNotEqual(first_revision, second_revision)

        run_import(self.root, dry_run=True)

        with sqlite3.connect(content_path) as database:
            self.assertEqual(
                database.execute(
                    "SELECT value FROM content_metadata WHERE key = 'revision'"
                ).fetchone()[0],
                second_revision,
            )

    def test_changed_kaikki_source_rebuilds_the_index(self) -> None:
        self.write_sources("talo - house\n")
        run_import(self.root)
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        with path.open("a", encoding="utf-8") as source:
            source.write("\n")
        report = run_import(self.root, dry_run=True)
        self.assertTrue(report.kaikki_index_rebuilt)

    def test_report_uses_canonical_form_and_lists_alternatives(self) -> None:
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        with path.open("a", encoding="utf-8") as source:
            source.write(json.dumps({"word": "talo", "lang_code": "fi", "forms": [{"form": "talojen", "source": "declension", "tags": ["genitive", "singular"]}]}) + "\n")
        self.write_sources("talo - house\n")
        report = run_import(self.root)
        self.assertEqual(report.form_alternatives["talo"]["nominal:genitive"], ["talojen"])

    def test_pronoun_forms_are_assigned_to_their_singular_or_plural_lemma(self) -> None:
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        pronoun_entry = {
            "word": "ne",
            "lang_code": "fi",
            "inflection_templates": [{"name": "fi-decl-pron/se"}],
            "forms": [
                {"form": "se", "source": "inflection", "tags": ["nominative", "singular"]},
                {"form": "sen", "source": "inflection", "tags": ["genitive", "singular"]},
                {"form": "sitä", "source": "inflection", "tags": ["partitive", "singular"]},
                {"form": "se", "source": "inflection", "tags": ["accusative", "singular"]},
                {"form": "siinä", "source": "inflection", "tags": ["inessive", "singular"]},
                {"form": "siitä", "source": "inflection", "tags": ["elative", "singular"]},
                {"form": "siihen", "source": "inflection", "tags": ["illative", "singular"]},
                {"form": "ne", "source": "inflection", "tags": ["nominative", "plural"]},
                {"form": "niiden", "source": "inflection", "tags": ["genitive", "plural"]},
                {"form": "niitä", "source": "inflection", "tags": ["partitive", "plural"]},
                {"form": "ne", "source": "inflection", "tags": ["accusative", "plural"]},
                {"form": "niissä", "source": "inflection", "tags": ["inessive", "plural"]},
                {"form": "niistä", "source": "inflection", "tags": ["elative", "plural"]},
                {"form": "niihin", "source": "inflection", "tags": ["illative", "plural"]},
            ],
        }
        with path.open("a", encoding="utf-8") as source:
            source.write(json.dumps(pronoun_entry) + "\n")
        self.write_sources("se - it\nne - they\n")

        report = run_import(self.root)

        self.assertEqual(report.missing_lexicon_profiles, [])
        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            singular_forms = database.execute(
                "SELECT card_key, form FROM word_forms JOIN vocabulary ON vocabulary.id = vocabulary_id WHERE finnish = 'se' ORDER BY card_key"
            ).fetchall()
            plural_forms = database.execute(
                "SELECT card_key, form FROM word_forms JOIN vocabulary ON vocabulary.id = vocabulary_id WHERE finnish = 'ne' ORDER BY card_key"
            ).fetchall()
        self.assertIn(("nominal:partitive", "sitä"), singular_forms)
        self.assertIn(("nominal:inessive", "siinä"), singular_forms)
        self.assertNotIn(("nominal:nominative", "se"), singular_forms)
        self.assertNotIn(("nominal:accusative", "se"), singular_forms)
        self.assertNotIn(("nominal-plural:partitive", "niitä"), singular_forms)
        self.assertIn(("nominal-plural:partitive", "niitä"), plural_forms)
        self.assertIn(("nominal-plural:inessive", "niissä"), plural_forms)
        self.assertNotIn(("nominal-plural:accusative", "ne"), plural_forms)
        self.assertNotIn(("nominal:partitive", "sitä"), plural_forms)
        self.assertFalse(any(card_key.startswith("nominal:") for card_key, _ in plural_forms))

    def test_personal_pronouns_receive_accusative_cards_only(self) -> None:
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        entries = [
            ("minä", "me", "minut", "meidät"),
            ("sinä", "te", "sinut", "teidät"),
            ("hän", "he", "hänet", "heidät"),
        ]
        with path.open("a", encoding="utf-8") as source:
            source.write(json.dumps({
                "word": "talo",
                "lang_code": "fi",
                "forms": [{"form": "talon", "source": "declension", "tags": ["accusative", "genitive", "singular"]}],
            }) + "\n")
            for singular, plural, singular_accusative, plural_accusative in entries:
                source.write(json.dumps({
                    "word": plural,
                    "lang_code": "fi",
                    "pos": "pron",
                    "forms": [
                        {"form": singular, "source": "declension", "tags": ["nominative", "singular"]},
                        {"form": singular_accusative, "source": "declension", "tags": ["accusative", "singular"]},
                        {"form": f"{singular}n", "source": "declension", "tags": ["genitive", "singular"]},
                        {"form": plural, "source": "declension", "tags": ["nominative", "plural"]},
                        {"form": plural_accusative, "source": "declension", "tags": ["accusative", "plural"]},
                        {"form": f"{plural}n", "source": "declension", "tags": ["genitive", "plural"]},
                    ],
                }) + "\n")
        self.write_sources("minä - I\nsinä - you\nhän - he / she\nme - we\nte - you (pl)\nhe - they\ntalo - house\n")

        run_import(self.root)

        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            accusatives = database.execute(
                "SELECT vocabulary.finnish, word_forms.card_key, word_forms.form, word_forms.prompt_label FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id WHERE word_forms.card_key LIKE '%:accusative' ORDER BY vocabulary.finnish"
            ).fetchall()
        self.assertEqual(accusatives, [
            ("he", "nominal-plural:accusative", "heidät", "Akkusatiivi"),
            ("hän", "nominal:accusative", "hänet", "Akkusatiivi"),
            ("me", "nominal-plural:accusative", "meidät", "Akkusatiivi"),
            ("minä", "nominal:accusative", "minut", "Akkusatiivi"),
            ("sinä", "nominal:accusative", "sinut", "Akkusatiivi"),
            ("te", "nominal-plural:accusative", "teidät", "Akkusatiivi"),
        ])

    def test_missing_kaikki_source_and_index_is_fatal_and_preserves_databases(self) -> None:
        self.write_sources("talo - house\n")
        (self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl").unlink()
        data_dir = self.root / "data"
        data_dir.mkdir()
        content_path, progress_path = data_dir / "content.sqlite", data_dir / "progress.sqlite"
        content_path.write_bytes(b"existing-content")
        progress_path.write_bytes(b"persistent-progress")
        with self.assertRaises(ImportValidationError) as raised:
            run_import(self.root)
        self.assertIn("missing Kaikki source and index", raised.exception.report.fatal_errors[0])
        self.assertEqual(content_path.read_bytes(), b"existing-content")
        self.assertEqual(progress_path.read_bytes(), b"persistent-progress")

    def test_frequency_error_preserves_existing_databases(self) -> None:
        self.write_sources("talo - house\n")
        data_dir = self.root / "data"
        data_dir.mkdir()
        content_path = data_dir / "content.sqlite"
        content_path.write_bytes(b"existing-content")
        (self.root / "frequency" / "fi_50k.txt").write_text("talo nope\n", encoding="utf-8")
        with self.assertRaises(ImportValidationError):
            run_import(self.root)
        self.assertEqual(content_path.read_bytes(), b"existing-content")

    def test_sentence_import_and_dry_run_preserve_content_and_progress(self) -> None:
        self.write_sources("talo - house\n", {"lesson.txt": "Talo on suuri. - The house is big. / A large house.\n"})
        data_dir = self.root / "data"
        data_dir.mkdir()
        content_path, progress_path = data_dir / "content.sqlite", data_dir / "progress.sqlite"
        content_path.write_bytes(b"existing-content")
        progress_path.write_bytes(b"persistent-progress")
        run_import(self.root, dry_run=True)
        self.assertEqual(content_path.read_bytes(), b"existing-content")
        self.assertEqual(progress_path.read_bytes(), b"persistent-progress")

    def test_main_exits_non_zero_for_fatal_error(self) -> None:
        report = ImportReport(fatal_errors=["missing Kaikki source"])
        with patch("backend.pipeline.run_import", side_effect=ImportValidationError(report)):
            with patch("sys.argv", ["pipeline"]):
                with self.assertRaises(SystemExit) as raised:
                    main()
        self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
