from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


INDEX_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE candidates (
    lemma TEXT NOT NULL,
    profile TEXT NOT NULL,
    slot TEXT NOT NULL,
    form TEXT NOT NULL,
    source_order INTEGER NOT NULL
);
CREATE INDEX idx_candidates_lookup ON candidates(lemma, profile, slot, source_order);
"""
INDEX_VERSION = 12
RECOMMENDATION_INDEX_VERSION = 5
PRONOUN_TEMPLATE_PREFIX = "fi-decl-pron/"
PERSONAL_PRONOUNS = frozenset({"minä", "sinä", "hän", "me", "te", "he"})
PERSONAL_PRONOUN_ACCUSATIVE_SLOT = ("accusative", "Akkusatiivi", {"accusative"})
PLURAL_NOMINAL_POS = frozenset({"noun", "adj", "pron", "det", "num"})
PLURAL_PARTITIVE_SLOT = ("partitive-plural", "Partitiivi, monikko (mitä?)", {"partitive", "plural"})
PLURAL_GENITIVE_SLOT = ("genitive-plural", "Genetiivi, monikko (minkä?)", {"genitive", "plural"})

NOMINAL_SLOTS = (
    ("nominative-plural", "Nominatiivi, monikko (mitkä?)", {"nominative", "plural"}),
    ("genitive", "Genetiivi (minkä?)", {"genitive", "singular"}),
    ("partitive", "Partitiivi (mitä?)", {"partitive", "singular"}),
    ("inessive", "Inessiivi (missä?)", {"inessive", "singular"}),
    ("elative", "Elatiivi (mistä?)", {"elative", "singular"}),
    ("illative", "Illatiivi (mihin?)", {"illative", "singular"}),
    ("adessive", "Adessiivi (millä?)", {"adessive", "singular"}),
    ("ablative", "Ablatiivi (miltä?)", {"ablative", "singular"}),
    ("allative", "Allatiivi (mille?)", {"allative", "singular"}),
)
NOMINAL_PLURAL_SLOTS = (
    ("nominative", "Nominatiivi, monikko (mitkä?)", {"nominative", "plural"}),
    ("genitive", "Genetiivi, monikko (minkä?)", {"genitive", "plural"}),
    ("partitive", "Partitiivi, monikko (mitä?)", {"partitive", "plural"}),
    ("inessive", "Inessiivi, monikko (missä?)", {"inessive", "plural"}),
    ("elative", "Elatiivi, monikko (mistä?)", {"elative", "plural"}),
    ("illative", "Illatiivi, monikko (mihin?)", {"illative", "plural"}),
    ("adessive", "Adessiivi, monikko (millä?)", {"adessive", "plural"}),
    ("ablative", "Ablatiivi, monikko (miltä?)", {"ablative", "plural"}),
    ("allative", "Allatiivi, monikko (mille?)", {"allative", "plural"}),
)
VERB_SLOTS = (
    ("present-1sg", "minä ____", {"indicative", "present", "first-person", "singular"}),
    ("present-2sg", "sinä ____", {"indicative", "present", "second-person", "singular"}),
    ("present-3sg", "hän ____", {"indicative", "present", "third-person", "singular"}),
    ("present-1pl", "me ____", {"indicative", "present", "first-person", "plural"}),
    ("present-2pl", "te ____", {"indicative", "present", "second-person", "plural"}),
    ("present-3pl", "he ____", {"indicative", "present", "third-person", "plural"}),
)
DISALLOWED_TAGS = {"rare", "possessive", "singular-possessive", "plural-possessive", "negative", "passive", "connegative", "accusative"}
NORMALIZABLE_NOMINAL_TAGS = {"nominative", "genitive", "partitive", "inessive", "elative", "illative", "adessive", "ablative", "allative", "essive", "translative", "abessive", "instructive", "comitative"}


@dataclass(frozen=True)
class GeneratedForm:
    card_key: str
    form: str
    profile: str
    prompt_label: str


def _source_signature(path: Path, words: set[str]) -> str:
    stat = path.stat()
    encoded_words = "\0".join(sorted(words)).encode("utf-8")
    return f"{INDEX_VERSION}:{stat.st_size}:{stat.st_mtime_ns}:{hashlib.sha256(encoded_words).hexdigest()}"


def _slots_for(
    form: dict[str, object], *, plural_nominal: bool = False, allow_personal_pronoun_accusative: bool = False,
    allow_plural_partitive: bool = False, allow_plural_genitive: bool = False,
) -> list[tuple[str, str, str]]:
    text = form.get("form")
    source = form.get("source")
    raw_tags = form.get("tags", [])
    if not isinstance(text, str) or not isinstance(source, str) or not isinstance(raw_tags, list):
        return []
    tags = {tag for tag in raw_tags if isinstance(tag, str)}
    if not text or text == "-" or " " in text or tags.intersection(DISALLOWED_TAGS - {"accusative"}):
        return []
    is_nominal = source in {"declension", "inflection"}
    slots = NOMINAL_PLURAL_SLOTS if is_nominal and plural_nominal else NOMINAL_SLOTS if is_nominal else VERB_SLOTS if source == "conjugation" else ()
    profile = "nominal-plural" if is_nominal and plural_nominal else "nominal" if is_nominal else "verb" if source == "conjugation" else ""
    if "accusative" in tags:
        slot, label, _ = PERSONAL_PRONOUN_ACCUSATIVE_SLOT
        return [(profile, slot, label)] if is_nominal and allow_personal_pronoun_accusative else []
    if is_nominal and not plural_nominal and allow_plural_partitive:
        slots = (*slots, PLURAL_PARTITIVE_SLOT)
    if is_nominal and not plural_nominal and allow_plural_genitive:
        slots = (*slots, PLURAL_GENITIVE_SLOT)
    return [(profile, slot, label) for slot, label, required in slots if required.issubset(tags)]


def _is_normalizable_form(source: str, tags: set[str]) -> bool:
    return source == "conjugation" or (source in {"declension", "inflection"} and bool(tags.intersection(NORMALIZABLE_NOMINAL_TAGS)))


def _owned_lemmas(entry: dict[str, object], lemmas: set[str]) -> set[str]:
    """Return requested lemmas represented by a Kaikki entry.

    Finnish pronouns may be inflected on a related entry.  For example, the
    entry headed by ``ne`` declares the ``fi-decl-pron/se`` template and
    contains the singular forms of ``se``.
    """
    owned: set[str] = set()
    word = entry.get("word")
    if isinstance(word, str) and word.casefold() in lemmas:
        owned.add(word.casefold())
    templates = entry.get("inflection_templates", [])
    if not isinstance(templates, list):
        return owned
    for template in templates:
        if not isinstance(template, dict):
            continue
        name = template.get("name")
        if not isinstance(name, str) or not name.startswith(PRONOUN_TEMPLATE_PREFIX):
            continue
        lemma = name.removeprefix(PRONOUN_TEMPLATE_PREFIX).casefold()
        if lemma in lemmas:
            owned.add(lemma)
    return owned


def _is_pronoun_entry(entry: dict[str, object]) -> bool:
    if entry.get("pos") == "pron":
        return True
    templates = entry.get("inflection_templates", [])
    return isinstance(templates, list) and any(
        isinstance(template, dict)
        and isinstance(template.get("name"), str)
        and template["name"].startswith("fi-decl-pron")
        for template in templates
    )


def _pronoun_owners(entry: dict[str, object], lemmas: set[str]) -> dict[str, str]:
    """Map requested pronoun lemmas to the number of their nominative form."""
    owners: dict[str, str] = {}
    for raw_form in entry.get("forms", []):
        if not isinstance(raw_form, dict):
            continue
        form = raw_form.get("form")
        source = raw_form.get("source")
        raw_tags = raw_form.get("tags", [])
        if not isinstance(form, str) or source not in {"declension", "inflection"} or not isinstance(raw_tags, list):
            continue
        tags = {tag for tag in raw_tags if isinstance(tag, str)}
        if "nominative" not in tags:
            continue
        number = "singular" if "singular" in tags else "plural" if "plural" in tags else None
        lemma = form.casefold()
        if number and lemma in lemmas:
            owners[lemma] = number
    return owners


def ensure_index(source_path: Path, index_path: Path, words: set[str]) -> bool:
    """Build the reusable subset index when its Kaikki source has changed.

    Returns True when a new index was built.
    """
    signature = _source_signature(source_path, words)
    if index_path.exists():
        with sqlite3.connect(index_path) as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = 'source_signature'").fetchone()
        if row and row[0] == signature:
            return False

    temporary_path = index_path.with_suffix(".tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temporary_path) as connection:
            connection.executescript(INDEX_SCHEMA)
            batch: list[tuple[str, str, str, str, int]] = []
            pronoun_numbers: dict[str, set[str]] = {}
            lemmas = {word.casefold() for word in words}
            encodings = {
                json.dumps(word, ensure_ascii=ensure_ascii)
                for word in words
                for ensure_ascii in (False, True)
            }
            word_pattern = r'"word"\s*:\s*(?:' + "|".join(re.escape(encoded) for encoded in encodings) + r')'
            form_pattern = r'"form"\s*:\s*(?:' + "|".join(re.escape(encoded) for encoded in encodings) + r')'
            template_encodings = {
                json.dumps(f"{PRONOUN_TEMPLATE_PREFIX}{lemma}", ensure_ascii=ensure_ascii)
                for lemma in lemmas
                for ensure_ascii in (False, True)
            }
            template_pattern = r'"name"\s*:\s*(?:' + "|".join(re.escape(encoded) for encoded in template_encodings) + r')'
            pattern = re.compile(f"(?:{word_pattern}|{form_pattern}|{template_pattern})") if encodings else None
            with source_path.open(encoding="utf-8") as source:
                for source_order, line in enumerate(source):
                    if pattern is None or not pattern.search(line):
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("lang_code") != "fi" or not isinstance(entry.get("word"), str):
                        continue
                    entry_pos = entry.get("pos")
                    allow_plural_partitive = entry_pos in PLURAL_NOMINAL_POS
                    allow_plural_genitive = entry_pos in PLURAL_NOMINAL_POS
                    entry_lemmas = _owned_lemmas(entry, lemmas)
                    pronoun_owners = _pronoun_owners(entry, lemmas) if _is_pronoun_entry(entry) else {}
                    for lemma, number in pronoun_owners.items():
                        pronoun_numbers.setdefault(lemma, set()).add(number)
                    if not entry_lemmas and not pronoun_owners:
                        continue
                    for raw_form in entry.get("forms", []):
                        if not isinstance(raw_form, dict):
                            continue
                        raw_tags = raw_form.get("tags", [])
                        tags = {tag for tag in raw_tags if isinstance(tag, str)} if isinstance(raw_tags, list) else set()
                        for lemma, number in pronoun_owners.items():
                            if number not in tags:
                                continue
                            for profile, slot, _ in _slots_for(
                                raw_form,
                                plural_nominal=number == "plural",
                                allow_personal_pronoun_accusative=lemma in PERSONAL_PRONOUNS,
                                allow_plural_partitive=allow_plural_partitive,
                                allow_plural_genitive=allow_plural_genitive,
                            ):
                                batch.append((lemma, profile, slot, raw_form["form"], source_order))
                        if pronoun_owners:
                            continue
                        for lemma in entry_lemmas:
                            for profile, slot, _ in _slots_for(
                                raw_form,
                                allow_personal_pronoun_accusative=lemma in PERSONAL_PRONOUNS,
                                allow_plural_partitive=allow_plural_partitive,
                                allow_plural_genitive=allow_plural_genitive,
                            ):
                                batch.append((lemma, profile, slot, raw_form["form"], source_order))
                    if len(batch) >= 10_000:
                        connection.executemany(
                            "INSERT INTO candidates (lemma, profile, slot, form, source_order) VALUES (?, ?, ?, ?, ?)", batch
                        )
                        batch.clear()
            if batch:
                connection.executemany(
                    "INSERT INTO candidates (lemma, profile, slot, form, source_order) VALUES (?, ?, ?, ?, ?)", batch
                )
            for lemma, numbers in pronoun_numbers.items():
                if "plural" in numbers:
                    connection.execute("DELETE FROM candidates WHERE lemma = ? AND profile = 'nominal'", (lemma,))
                if "singular" in numbers:
                    connection.execute(
                        "DELETE FROM candidates WHERE lemma = ? AND profile = 'nominal' AND slot = 'nominative-plural'",
                        (lemma,),
                    )
            connection.execute("INSERT INTO metadata VALUES ('source_signature', ?)", (signature,))
        temporary_path.replace(index_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def generated_forms(index_path: Path, word: str) -> tuple[list[GeneratedForm], dict[str, list[str]]]:
    forms: list[GeneratedForm] = []
    alternatives: dict[str, list[str]] = {}
    labels = {("nominal", slot): label for slot, label, _ in NOMINAL_SLOTS}
    labels[("nominal", PLURAL_PARTITIVE_SLOT[0])] = PLURAL_PARTITIVE_SLOT[1]
    labels[("nominal", PLURAL_GENITIVE_SLOT[0])] = PLURAL_GENITIVE_SLOT[1]
    labels.update({("nominal-plural", slot): label for slot, label, _ in NOMINAL_PLURAL_SLOTS})
    labels.update({(profile, PERSONAL_PRONOUN_ACCUSATIVE_SLOT[0]): PERSONAL_PRONOUN_ACCUSATIVE_SLOT[1] for profile in ("nominal", "nominal-plural")})
    labels.update({("verb", slot): label for slot, label, _ in VERB_SLOTS})
    with sqlite3.connect(index_path) as connection:
        rows = connection.execute(
            """SELECT profile, slot, form FROM candidates WHERE lemma = ?
               ORDER BY profile, slot, source_order""",
            (word.casefold(),),
        ).fetchall()
    grouped: dict[tuple[str, str], list[str]] = {}
    for profile, slot, form in rows:
        grouped.setdefault((profile, slot), []).append(form)
    for (profile, slot), candidates in sorted(grouped.items()):
        unique = list(dict.fromkeys(candidates))
        if not unique:
            continue
        card_key = f"{profile}:{slot}"
        forms.append(GeneratedForm(card_key, unique[0], profile, labels[(profile, slot)]))
        if len(unique) > 1:
            alternatives[card_key] = unique[1:]
    return forms, alternatives


RECOMMENDATION_INDEX_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE surface_lemmas (surface TEXT NOT NULL, lemma TEXT NOT NULL, PRIMARY KEY (surface, lemma));
CREATE INDEX idx_surface_lemmas_surface ON surface_lemmas(surface);
"""


def _recommendation_signature(path: Path, surfaces: set[str]) -> str:
    stat = path.stat()
    encoded = "\0".join(sorted(surfaces)).encode("utf-8")
    return f"{RECOMMENDATION_INDEX_VERSION}:{stat.st_size}:{stat.st_mtime_ns}:{hashlib.sha256(encoded).hexdigest()}"


def ensure_recommendation_index(source_path: Path, index_path: Path, surfaces: set[str]) -> bool:
    """Build a small reverse morphology cache for recommendation candidates."""
    signature = _recommendation_signature(source_path, surfaces)
    if index_path.exists():
        with sqlite3.connect(index_path) as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = 'source_signature'").fetchone()
        if row and row[0] == signature:
            return False

    temporary_path = index_path.with_suffix(".tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temporary_path) as connection:
            connection.executescript(RECOMMENDATION_INDEX_SCHEMA)
            encodings = {json.dumps(surface, ensure_ascii=ensure_ascii) for surface in surfaces for ensure_ascii in (False, True)}
            surface_pattern = r'(?:"form"|"word")\s*:\s*(?:' + "|".join(re.escape(encoded) for encoded in encodings) + r')'
            pattern = re.compile(surface_pattern) if encodings else None
            batch: list[tuple[str, str]] = []
            with source_path.open(encoding="utf-8") as source:
                for line in source:
                    if pattern is None or not pattern.search(line):
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    lemma = entry.get("word")
                    if entry.get("lang_code") != "fi" or not isinstance(lemma, str) or " " in lemma:
                        continue
                    senses = entry.get("senses", [])
                    if lemma.casefold() in surfaces and isinstance(senses, list) and any(
                        isinstance(sense, dict) and not sense.get("form_of") for sense in senses
                    ):
                        batch.append((lemma.casefold(), lemma.casefold()))
                    for raw_form in entry.get("forms", []):
                        if not isinstance(raw_form, dict):
                            continue
                        surface = raw_form.get("form")
                        source_name = raw_form.get("source")
                        raw_tags = raw_form.get("tags", [])
                        if not isinstance(surface, str) or not isinstance(source_name, str) or not isinstance(raw_tags, list):
                            continue
                        tags = {tag for tag in raw_tags if isinstance(tag, str)}
                        if surface.casefold() not in surfaces or not _is_normalizable_form(source_name, tags):
                            continue
                        if not surface or surface == "-" or " " in surface or tags.intersection(DISALLOWED_TAGS):
                            continue
                        batch.append((surface.casefold(), lemma.casefold()))
            if batch:
                connection.executemany("INSERT OR IGNORE INTO surface_lemmas (surface, lemma) VALUES (?, ?)", batch)
            connection.execute("INSERT INTO metadata VALUES ('source_signature', ?)", (signature,))
        temporary_path.replace(index_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def recommendation_lemmas(index_path: Path) -> dict[str, str]:
    """Return only unambiguous surface-to-lemma mappings from the cache."""
    if not index_path.exists():
        return {}
    with sqlite3.connect(index_path) as connection:
        rows = connection.execute(
            "SELECT surface, GROUP_CONCAT(lemma), COUNT(*) FROM surface_lemmas GROUP BY surface HAVING COUNT(*) = 1"
        ).fetchall()
    return {surface: lemma for surface, lemma, _ in rows}
