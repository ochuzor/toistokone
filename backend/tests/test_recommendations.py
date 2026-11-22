from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
