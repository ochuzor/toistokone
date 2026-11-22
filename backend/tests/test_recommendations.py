from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.app.recommendations import get_recommendations
from backend.pipeline import run_import
from backend.tests.kaikki_fixture import write_kaikki


class RecommendationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "frequency").mkdir()
        (self.root / "sentences").mkdir()
        write_kaikki(self.root)
        (self.root / "frequency" / "fi_50k.txt").write_text(
            "kuin 110\nyleinen 100\nkonteksti 90\nja 80\nauto 70\nautossa 60\nirrallinen 50\n",
            encoding="utf-8",
        )
        (self.root / "dictionary.txt").write_text("auto - car\ntalo - house\nkuin - than\n", encoding="utf-8")
        (self.root / "sentences" / "lesson.txt").write_text(
            "Talo konteksti. - House context.\n"
            "Auto konteksti yleinen ja. - Car context common.\n"
            "Auto kuin. - Like a car.\n"
            "Autossa yleinen. - Common in the car.\n"
            "Irrallinen. - Isolated.\n",
            encoding="utf-8",
        )
        run_import(self.root)
        self.content_path = self.root / "data" / "content.sqlite"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_recommendations_are_contextual_frequency_first_and_exclude_known_or_short_words(self) -> None:
        recommendations = get_recommendations(self.content_path)

        self.assertEqual([recommendation["word"] for recommendation in recommendations], ["yleinen", "konteksti"])
        self.assertNotIn("kuin", [recommendation["word"] for recommendation in recommendations])
        self.assertEqual(recommendations[0]["related_vocabulary_count"], 1)
        self.assertEqual(recommendations[1]["related_vocabulary_count"], 2)
        self.assertEqual(recommendations[0]["examples"][0], {
            "finnish": "Auto konteksti yleinen ja.",
            "english_translations": ["Car context common."],
        })

    def test_recommendations_are_empty_without_contextual_frequency_words(self) -> None:
        (self.root / "frequency" / "fi_50k.txt").write_text("irrallinen 50\n", encoding="utf-8")
        run_import(self.root)

        self.assertEqual(get_recommendations(self.content_path), [])

    def test_recommendations_merge_unambiguous_forms_and_keep_ambiguous_surfaces(self) -> None:
        source = self.root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
        entries = [
            {"word": "ravintola", "lang_code": "fi", "forms": [
                {"form": "ravintolassa", "source": "declension", "tags": ["inessive", "singular"]},
                {"form": "ravintolasta", "source": "declension", "tags": ["elative", "singular"]},
            ]},
            {"word": "pankki", "lang_code": "fi", "forms": [
                {"form": "pankissa", "source": "declension", "tags": ["inessive", "singular"]},
            ]},
            {"word": "penkki", "lang_code": "fi", "forms": [
                {"form": "pankissa", "source": "declension", "tags": ["inessive", "singular"]},
            ]},
            {"word": "joka", "lang_code": "fi", "forms": [
                {"form": "joten", "source": "inflection", "tags": ["causative", "singular"]},
            ]},
            {"word": "hyvä", "lang_code": "fi", "forms": [
                {"form": "hyvin", "source": "declension", "tags": ["instructive", "plural"]},
            ]},
            {"word": "hyvin", "lang_code": "fi", "senses": [{"glosses": ["well"]}]},
        ]
        with source.open("a", encoding="utf-8") as file:
            file.write("".join(json.dumps(entry) + "\n" for entry in entries))
        (self.root / "frequency" / "fi_50k.txt").write_text(
            "ravintolassa 120\nravintolasta 110\npankissa 100\nhyvin 95\njoten 90\nauto 80\ntalo 70\n",
            encoding="utf-8",
        )
        (self.root / "sentences" / "lesson.txt").write_text(
            "Auto ravintolassa. - A car in the restaurant.\n"
            "Talo ravintolasta. - From the restaurant.\n"
            "Auto pankissa. - A car in the bank.\n"
            "Auto hyvin. - A car well.\n"
            "Auto joten. - A car therefore.\n",
            encoding="utf-8",
        )

        run_import(self.root)
        recommendations = get_recommendations(self.content_path)

        restaurant = next(item for item in recommendations if item["word"] == "ravintola")
        self.assertEqual(restaurant["observed_forms"], ["ravintolassa", "ravintolasta"])
        self.assertEqual(restaurant["related_vocabulary_count"], 2)
        self.assertEqual(sum(item["word"] == "ravintola" for item in recommendations), 1)
        self.assertIn("pankissa", [item["word"] for item in recommendations])
        self.assertIn("hyvin", [item["word"] for item in recommendations])
        self.assertIn("joten", [item["word"] for item in recommendations])


if __name__ == "__main__":
    unittest.main()
