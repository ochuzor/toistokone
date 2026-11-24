from __future__ import annotations

import json
from pathlib import Path


def write_kaikki(root: Path) -> None:
    lexicon = root / "lexicon"
    lexicon.mkdir(exist_ok=True)
    entries = [
        {"word": "talo", "lang_code": "fi", "forms": [
            {"form": "talo", "source": "declension", "tags": ["nominative", "singular"]},
            {"form": "talot", "source": "declension", "tags": ["nominative", "plural"]},
            {"form": "talon", "source": "declension", "tags": ["genitive", "singular"]},
            {"form": "taloa", "source": "declension", "tags": ["partitive", "singular"]},
            {"form": "talossa", "source": "declension", "tags": ["inessive", "singular"]},
            {"form": "talosta", "source": "declension", "tags": ["elative", "singular"]},
            {"form": "taloon", "source": "declension", "tags": ["illative", "singular"]},
            {"form": "talolla", "source": "declension", "tags": ["adessive", "singular"]},
            {"form": "talolta", "source": "declension", "tags": ["ablative", "singular"]},
            {"form": "talolle", "source": "declension", "tags": ["allative", "singular"]},
        ]},
        {"word": "ruoka", "lang_code": "fi", "forms": [
            {"form": "ruoka", "source": "declension", "tags": ["nominative", "singular"]},
            {"form": "ruoat", "source": "declension", "tags": ["nominative", "plural"]},
            {"form": "ruoan", "source": "declension", "tags": ["genitive", "singular"]},
            {"form": "ruokaa", "source": "declension", "tags": ["partitive", "singular"]},
            {"form": "ruoassa", "source": "declension", "tags": ["inessive", "singular"]},
            {"form": "ruoasta", "source": "declension", "tags": ["elative", "singular"]},
            {"form": "ruokaan", "source": "declension", "tags": ["illative", "singular"]},
        ]},
        {"word": "auto", "lang_code": "fi", "forms": [
            {"form": "auto", "source": "declension", "tags": ["nominative", "singular"]},
            {"form": "autot", "source": "declension", "tags": ["nominative", "plural"]},
            {"form": "auton", "source": "declension", "tags": ["genitive", "singular"]},
            {"form": "autoa", "source": "declension", "tags": ["partitive", "singular"]},
            {"form": "autossa", "source": "declension", "tags": ["inessive", "singular"]},
            {"form": "autosta", "source": "declension", "tags": ["elative", "singular"]},
            {"form": "autoon", "source": "declension", "tags": ["illative", "singular"]},
        ]},
        {"word": "tehdä", "lang_code": "fi", "forms": [
            {"form": "teen", "source": "conjugation", "tags": ["indicative", "present", "first-person", "singular"]},
            {"form": "teet", "source": "conjugation", "tags": ["indicative", "present", "second-person", "singular"]},
            {"form": "tekee", "source": "conjugation", "tags": ["indicative", "present", "third-person", "singular"]},
            {"form": "teemme", "source": "conjugation", "tags": ["indicative", "present", "first-person", "plural"]},
            {"form": "teette", "source": "conjugation", "tags": ["indicative", "present", "second-person", "plural"]},
            {"form": "tekevät", "source": "conjugation", "tags": ["indicative", "present", "third-person", "plural"]},
        ]},
    ]
    (lexicon / "kaikki.org-dictionary-Finnish-words.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")
