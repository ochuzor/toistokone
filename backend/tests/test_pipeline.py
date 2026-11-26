from __future__ import annotations

import json
import io
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
        self.assertEqual(report.form_count, 28)
        self.assertEqual(report.missing_lexicon_profiles, ["particle"])
        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            talo = database.execute("SELECT card_key, form, profile, prompt_label FROM word_forms JOIN vocabulary ON vocabulary.id = vocabulary_id WHERE finnish = 'talo' ORDER BY card_key").fetchall()
            verb = database.execute("SELECT card_key, form, prompt_label FROM word_forms JOIN vocabulary ON vocabulary.id = vocabulary_id WHERE finnish = 'tehdä' ORDER BY card_key").fetchall()
        self.assertIn(("nominal:inessive", "talossa", "nominal", "Inessiivi (missä?)"), talo)
        self.assertIn(("nominal:adessive", "talolla", "nominal", "Adessiivi (millä?)"), talo)
        self.assertIn(("nominal:ablative", "talolta", "nominal", "Ablatiivi (miltä?)"), talo)
        self.assertIn(("nominal:allative", "talolle", "nominal", "Allatiivi (mille?)"), talo)
        self.assertIn(("nominal:essive", "talona", "nominal", "Essiivi (minä?)"), talo)
        self.assertNotIn(("nominal:nominative", "talo", "nominal", "Nominatiivi (mikä?)"), talo)
        self.assertIn(("nominal:nominative-plural", "talot", "nominal", "Nominatiivi, monikko (mitkä?)"), talo)
        self.assertIn(("verb:present-3sg", "tekee", "hän ____"), verb)
        self.assertIn(("verb:past-3sg", "teki", "hän ____"), verb)
        self.assertIn(("verb:conditional-3sg", "tekisi", "hän ____"), verb)
        self.assertEqual(len([card for card in verb if card[0].startswith("verb:past-")]), 6)
        self.assertEqual(len([card for card in verb if card[0].startswith("verb:conditional-")]), 6)
        self.assertNotIn(("verb:past-1sg", "en tehnyt", "minä ____"), verb)
        self.assertFalse(any(card[1] in {"en tekisi", "olisin tehnyt", "tehtäisiin"} for card in verb))
        self.assertFalse(any(card[1] == "tehtiin" for card in verb))
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

    def test_learning_sets_import_membership_and_report_coverage(self) -> None:
        words = ["talo", "tehdä", *[f"word-{number}" for number in range(1, 9)]]
        self.write_sources("".join(f"{word} - meaning\n" for word in words), {"lesson.txt": "Talossa asun. - I live in the house.\n"})
        directory = self.root / "learning-sets"
        directory.mkdir()
        (directory / "renamed-file.md").write_text("---\nid: home-life\n---\n\n# Home life\n\n" + "".join(f"- {word}\n" for word in words), encoding="utf-8")

        report = run_import(self.root)

        self.assertEqual(report.learning_set_file_count, 1)
        self.assertEqual(report.learning_set_coverage[0].title, "Home life")
        self.assertEqual(report.learning_set_coverage[0].word_count, 10)
        self.assertIn("## Learning-set coverage\n- Home life: 10 words", report.render(dry_run=False))
        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            membership = database.execute(
                "SELECT learning_sets.key, learning_sets.title, vocabulary.finnish "
                "FROM learning_sets JOIN learning_set_words ON learning_set_words.set_key = learning_sets.key "
                "JOIN vocabulary ON vocabulary.id = learning_set_words.vocabulary_id ORDER BY vocabulary.finnish"
            ).fetchall()
        self.assertEqual(len(membership), 10)
        self.assertIn(("home-life", "Home life", "talo"), membership)
        self.assertIn(("home-life", "Home life", "tehdä"), membership)

    def test_learning_set_unknown_or_duplicate_words_fail_import(self) -> None:
        self.write_sources("talo - house\n")
        directory = self.root / "learning-sets"
        directory.mkdir()
        (directory / "invalid.md").write_text("---\nid: invalid\n---\n# Invalid\n- talo\n- talo\n- puuttuu\n", encoding="utf-8")

        with self.assertRaises(ImportValidationError) as raised:
            run_import(self.root)

        errors = raised.exception.report.fatal_errors
        self.assertTrue(any("duplicate learning-set word 'talo'" in error for error in errors))
        self.assertTrue(any("unknown dictionary word 'puuttuu'" in error for error in errors))
        self.assertTrue(any("at least 10 dictionary words" in error for error in errors))

    def test_learning_set_ids_are_required_valid_and_unique(self) -> None:
        words = ["talo", *[f"word-{number}" for number in range(1, 10)]]
        self.write_sources("".join(f"{word} - meaning\n" for word in words))
        directory = self.root / "learning-sets"
        directory.mkdir()
        entries = "".join(f"- {word}\n" for word in words)
        (directory / "missing.md").write_text("# Missing ID\n" + entries, encoding="utf-8")
        (directory / "malformed.md").write_text("---\nid: Not Valid\n---\n# Malformed\n" + entries, encoding="utf-8")
        (directory / "first.md").write_text("---\nid: duplicate\n---\n# First\n" + entries, encoding="utf-8")
        (directory / "second.md").write_text("---\nid: duplicate\n---\n# Second\n" + entries, encoding="utf-8")

        with self.assertRaises(ImportValidationError) as raised:
            run_import(self.root)

        errors = raised.exception.report.fatal_errors
        self.assertTrue(any("expected opening '---'" in error for error in errors))
        self.assertTrue(any("must use lower-case kebab-case" in error for error in errors))
        self.assertTrue(any("conflicts with" in error and "first.md" in error for error in errors))

    def test_changed_kaikki_source_rebuilds_the_index(self) -> None:
        self.write_sources("talo - house\n")
        run_import(self.root)
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        with path.open("a", encoding="utf-8") as source:
            source.write("\n")
        report = run_import(self.root, dry_run=True)
        self.assertTrue(report.kaikki_index_rebuilt)

    def test_progress_reports_import_phases_and_cached_indexes(self) -> None:
        self.write_sources("talo - house\n", {"lesson.txt": "Talo on suuri. - The house is big.\n"})
        first_progress: list[str] = []

        run_import(self.root, dry_run=True, progress=first_progress.append)

        self.assertIn("Reading dictionary", first_progress)
        self.assertIn("Reading learning paths", first_progress)
        self.assertIn("Kaikki form index: rebuilding", first_progress)
        self.assertIn("Kaikki form index: complete", first_progress)
        self.assertIn("Reading sentences (1/1): lesson.txt", first_progress)
        self.assertIn("Recommendation lemma index: rebuilding", first_progress)
        self.assertIn("Analyzing content health", first_progress)
        self.assertIn("Dry run: skipping content database build", first_progress)
        self.assertEqual(first_progress[-1], "Writing import report")

        cached_progress: list[str] = []
        run_import(self.root, dry_run=True, progress=cached_progress.append)

        self.assertIn("Kaikki form index: reusing existing index", cached_progress)
        self.assertIn("Recommendation lemma index: reusing existing index", cached_progress)

    def test_report_uses_canonical_form_and_lists_alternatives(self) -> None:
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        with path.open("a", encoding="utf-8") as source:
            source.write(json.dumps({"word": "talo", "lang_code": "fi", "forms": [{"form": "talojen", "source": "declension", "tags": ["genitive", "singular"]}]}) + "\n")
        self.write_sources("talo - house\n")
        report = run_import(self.root)
        self.assertEqual(report.form_alternatives["talo"]["nominal:genitive"], ["talojen"])

    def test_capitalized_identical_entries_are_forms_only(self) -> None:
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
            source.write(json.dumps({
                "word": "Talo", "lang_code": "fi", "pos": "name",
                "forms": [{"form": "Talon-nimi", "source": "declension", "tags": ["genitive", "singular"]}],
            }) + "\n")
        self.write_sources("Helsinki - Helsinki\nsauna - sauna\nItävalta - Austria\ntalo - house\n")

        run_import(self.root)

        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            flags = database.execute(
                "SELECT finnish, meaning_quizzable FROM vocabulary ORDER BY finnish"
            ).fetchall()
            helsinki_forms = database.execute(
                "SELECT card_key, form FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id WHERE vocabulary.finnish = 'Helsinki' ORDER BY card_key"
            ).fetchall()
        self.assertEqual(flags, [("Helsinki", 0), ("Itävalta", 1), ("sauna", 1), ("talo", 1)])
        self.assertIn(("nominal:inessive", "Helsingissä"), helsinki_forms)
        talo_forms = database.execute(
            "SELECT form FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id WHERE vocabulary.finnish = 'talo'"
        ).fetchall()
        self.assertNotIn(("Talon-nimi",), talo_forms)

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
                {"form": "sillä", "source": "inflection", "tags": ["adessive", "singular"]},
                {"form": "siltä", "source": "inflection", "tags": ["ablative", "singular"]},
                {"form": "sille", "source": "inflection", "tags": ["allative", "singular"]},
                {"form": "ne", "source": "inflection", "tags": ["nominative", "plural"]},
                {"form": "niiden", "source": "inflection", "tags": ["genitive", "plural"]},
                {"form": "niitä", "source": "inflection", "tags": ["partitive", "plural"]},
                {"form": "ne", "source": "inflection", "tags": ["accusative", "plural"]},
                {"form": "niissä", "source": "inflection", "tags": ["inessive", "plural"]},
                {"form": "niistä", "source": "inflection", "tags": ["elative", "plural"]},
                {"form": "niihin", "source": "inflection", "tags": ["illative", "plural"]},
                {"form": "niillä", "source": "inflection", "tags": ["adessive", "plural"]},
                {"form": "niiltä", "source": "inflection", "tags": ["ablative", "plural"]},
                {"form": "niille", "source": "inflection", "tags": ["allative", "plural"]},
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
        self.assertIn(("nominal:adessive", "sillä"), singular_forms)
        self.assertNotIn(("nominal:nominative", "se"), singular_forms)
        self.assertNotIn(("nominal:accusative", "se"), singular_forms)
        self.assertNotIn(("nominal-plural:partitive", "niitä"), singular_forms)
        self.assertIn(("nominal-plural:partitive", "niitä"), plural_forms)
        self.assertIn(("nominal-plural:inessive", "niissä"), plural_forms)
        self.assertIn(("nominal-plural:adessive", "niillä"), plural_forms)
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
        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            duplicate_plural_genitives = database.execute(
                "SELECT COUNT(*) FROM word_forms WHERE card_key = 'nominal:genitive-plural'"
            ).fetchone()[0]
        self.assertEqual(duplicate_plural_genitives, 0)

    def test_plural_genitives_and_partitives_are_limited_to_supported_nominal_parts_of_speech(self) -> None:
        path = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        entries = [
            ("kana", "noun", "kanojen", "kanoja"),
            ("pieni", "adj", "pienten", "pieniä"),
            ("kolme", "num", "kolmien", "kolmia"),
            ("tämä", "det", "näiden", "näitä"),
            ("Suomi", "name", "Suomien", "Suomeja"),
            ("valmistunut", "verb", "valmistuneiden", "valmistuneita"),
        ]
        with path.open("a", encoding="utf-8") as source:
            for word, pos, plural_genitive, plural_partitive in entries:
                source.write(json.dumps({
                    "word": word,
                    "lang_code": "fi",
                    "pos": pos,
                    "forms": [
                        {"form": word, "source": "declension", "tags": ["nominative", "singular"]},
                        {"form": plural_genitive, "source": "declension", "tags": ["genitive", "plural"]},
                        {"form": plural_partitive, "source": "declension", "tags": ["partitive", "plural"]},
                    ],
                }) + "\n")
            source.write(json.dumps({
                "word": "ne",
                "lang_code": "fi",
                "pos": "pron",
                "forms": [
                    {"form": "ne", "source": "declension", "tags": ["nominative", "plural"]},
                    {"form": "niiden", "source": "declension", "tags": ["genitive", "plural"]},
                    {"form": "niitä", "source": "declension", "tags": ["partitive", "plural"]},
                ],
            }) + "\n")
        self.write_sources("kana - chicken\npieni - small\nkolme - three\nne - they\ntämä - this\nSuomi - Finland\nvalmistunut - graduated\n")

        run_import(self.root)

        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            forms = database.execute(
                "SELECT vocabulary.finnish, word_forms.form, word_forms.prompt_label FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id WHERE word_forms.card_key = 'nominal:partitive-plural' ORDER BY vocabulary.finnish"
            ).fetchall()
        self.assertEqual(forms, [
            ("kana", "kanoja", "Partitiivi, monikko (mitä?)"),
            ("kolme", "kolmia", "Partitiivi, monikko (mitä?)"),
            ("pieni", "pieniä", "Partitiivi, monikko (mitä?)"),
            ("tämä", "näitä", "Partitiivi, monikko (mitä?)"),
        ])
        genitives = database.execute(
            "SELECT vocabulary.finnish, word_forms.form, word_forms.prompt_label FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id WHERE word_forms.card_key = 'nominal:genitive-plural' ORDER BY vocabulary.finnish"
        ).fetchall()
        self.assertEqual(genitives, [
            ("kana", "kanojen", "Genetiivi, monikko (minkä?)"),
            ("kolme", "kolmien", "Genetiivi, monikko (minkä?)"),
            ("pieni", "pienten", "Genetiivi, monikko (minkä?)"),
            ("tämä", "näiden", "Genetiivi, monikko (minkä?)"),
        ])
        pronoun_genitives = database.execute(
            "SELECT vocabulary.finnish, word_forms.card_key, word_forms.form FROM word_forms JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id WHERE vocabulary.finnish = 'ne' AND word_forms.card_key LIKE '%:genitive'"
        ).fetchall()
        self.assertEqual(pronoun_genitives, [("ne", "nominal-plural:genitive", "niiden")])

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

    def test_learning_paths_import_ordered_set_membership_and_reject_invalid_references(self) -> None:
        words = ["talo", "ruoka", *[f"word-{number}" for number in range(1, 9)]]
        self.write_sources("".join(f"{word} - meaning\n" for word in words))
        sets = self.root / "learning-sets"
        sets.mkdir()
        for key, title in (("first", "First set"), ("second", "Second set")):
            (sets / f"{key}.md").write_text(
                f"---\nid: {key}\n---\n# {title}\n" + "".join(f"- {word}\n" for word in words), encoding="utf-8"
            )
        paths = self.root / "learning-paths"
        paths.mkdir()
        (paths / "journey.md").write_text("---\nid: journey\n---\n# My journey\n- first\n- second\n", encoding="utf-8")

        report = run_import(self.root)

        self.assertEqual(report.learning_path_file_count, 1)
        with sqlite3.connect(self.root / "data" / "content.sqlite") as database:
            self.assertEqual(database.execute("SELECT key, title FROM learning_paths").fetchall(), [("journey", "My journey")])
            self.assertEqual(database.execute("SELECT set_key FROM learning_path_sets WHERE path_key = 'journey' ORDER BY ordinal").fetchall(), [("first",), ("second",)])

        (paths / "invalid.md").write_text("---\nid: invalid\n---\n# Invalid\n- missing\n- first\n- first\n", encoding="utf-8")
        with self.assertRaises(ImportValidationError) as raised:
            run_import(self.root, dry_run=True)
        self.assertTrue(any("unknown learning-set ID 'missing'" in error for error in raised.exception.report.fatal_errors))
        self.assertTrue(any("duplicate learning-set ID 'first'" in error for error in raised.exception.report.fatal_errors))

    def test_frequency_error_preserves_existing_databases(self) -> None:
        self.write_sources("talo - house\n")
        data_dir = self.root / "data"
        data_dir.mkdir()
        content_path = data_dir / "content.sqlite"
        content_path.write_bytes(b"existing-content")
        (self.root / "frequency" / "fi_50k.txt").write_text("talo nope\n", encoding="utf-8")
        with patch("backend.pipeline.ensure_index") as ensure_index, patch("backend.pipeline.ensure_recommendation_index") as ensure_recommendation_index:
            with self.assertRaises(ImportValidationError):
                run_import(self.root)
        ensure_index.assert_not_called()
        ensure_recommendation_index.assert_not_called()
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
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("backend.pipeline.run_import", side_effect=ImportValidationError(report)), patch("sys.argv", ["pipeline"]), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "Import failed: content validation errors found. See data/import-report.md.\n")

    def test_main_points_to_the_report_without_printing_it(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("backend.pipeline.run_import", return_value=ImportReport()), patch("sys.argv", ["pipeline"]), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            main()

        self.assertEqual(stdout.getvalue(), "Import complete. See data/import-report.md.\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_report_renders_navigable_markdown_sections(self) -> None:
        report = ImportReport(
            fatal_errors=["missing Kaikki source"],
            skipped_lines=["dictionary.txt: line 2: empty field"],
        ).render(dry_run=True)

        self.assertTrue(report.startswith("# ToistoKone import report\n"))
        self.assertIn("## Import summary", report)
        self.assertIn("## Errors\n- missing Kaikki source", report)
        self.assertIn("## Diagnostics\n- dictionary.txt: line 2: empty field", report)


if __name__ == "__main__":
    unittest.main()
