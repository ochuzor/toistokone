from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.config import PROJECT_ROOT
from backend.app.content_health import ContentHealth, analyze_content_health
from backend.app.sentences import tokens
from backend.kaikki import GeneratedForm, ensure_index, ensure_recommendation_index, generated_forms, recommendation_lemmas


RECOMMENDATION_LEMMA_CANDIDATE_LIMIT = 100


@dataclass
class ImportReport:
    dictionary_file_count: int = 0
    frequency_file_count: int = 0
    sentence_file_count: int = 0
    vocabulary_count: int = 0
    form_count: int = 0
    sentence_count: int = 0
    translation_count: int = 0
    frequency_entry_count: int = 0
    duplicate_vocabulary_count: int = 0
    duplicate_sentence_count: int = 0
    duplicate_translation_count: int = 0
    kaikki_index_rebuilt: bool = False
    recommendation_lemma_index_rebuilt: bool = False
    missing_lexicon_profiles: list[str] = field(default_factory=list)
    form_alternatives: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    content_health: ContentHealth | None = None
    fatal_errors: list[str] = field(default_factory=list)
    skipped_lines: list[str] = field(default_factory=list)

    def render(self, *, dry_run: bool) -> str:
        lines = [
            "ToistoKone import report", f"Mode: {'dry run' if dry_run else 'normal'}",
            f"Dictionary files: {self.dictionary_file_count}", f"Frequency files: {self.frequency_file_count}",
            f"Sentence files: {self.sentence_file_count}", f"Kaikki index rebuilt: {'yes' if self.kaikki_index_rebuilt else 'no'}",
            f"Recommendation lemma index rebuilt: {'yes' if self.recommendation_lemma_index_rebuilt else 'no'}",
            f"Imported vocabulary: {self.vocabulary_count}", f"Imported grammar forms: {self.form_count}",
            f"Imported sentences: {self.sentence_count}", f"Imported translations: {self.translation_count}",
            f"Imported frequency entries: {self.frequency_entry_count}",
            f"Duplicate vocabulary entries: {self.duplicate_vocabulary_count}",
            f"Duplicate sentences: {self.duplicate_sentence_count}",
            f"Duplicate translations: {self.duplicate_translation_count}",
            f"Words without usable Kaikki profiles: {len(self.missing_lexicon_profiles)}",
            f"Form slots with alternatives: {sum(len(slots) for slots in self.form_alternatives.values())}",
            f"Errors: {len(self.fatal_errors)}", f"Skipped lines: {len(self.skipped_lines)}",
        ]
        if self.content_health:
            summary = self.content_health.summary()
            lines.extend([
                "Content health:",
                f"Base words without supporting sentences: {summary['base_without_sentences']}",
                f"Form cards with fewer than two supporting sentences: {summary['under_supported_forms']}",
                f"Sentences without tracked vocabulary or forms: {summary['untracked_sentences']}",
            ])
        if self.missing_lexicon_profiles:
            lines.extend(["", "Words without usable Kaikki profiles:", *[f"- {word}" for word in self.missing_lexicon_profiles]])
        if self.form_alternatives:
            lines.extend(["", "Alternative Kaikki forms (first candidate selected):"])
            for word in sorted(self.form_alternatives):
                lines.append(f"- {word}:")
                for slot, alternatives in sorted(self.form_alternatives[word].items()):
                    lines.append(f"  - {slot}: {' / '.join(alternatives)}")
        if self.content_health:
            if self.content_health.base_without_sentences:
                lines.extend(["", "Base words without supporting sentences:", *[f"- {word}" for word in self.content_health.base_without_sentences]])
            if self.content_health.under_supported_forms:
                lines.extend(["", "Form cards with fewer than two supporting sentences:"])
                by_base: dict[str, list] = {}
                for finding in self.content_health.under_supported_forms:
                    by_base.setdefault(finding.base_word, []).append(finding)
                for base_word, findings in by_base.items():
                    lines.append(f"- {base_word}:")
                    lines.extend(f"  - {finding.prompt_label}: {finding.form} ({finding.sentence_count})" for finding in findings)
            if self.content_health.untracked_sentences:
                lines.extend(["", "Sentences without tracked vocabulary or forms:", *[f"- {finding.finnish}" for finding in self.content_health.untracked_sentences]])
        if self.fatal_errors:
            lines.extend(["", "Errors:", *self.fatal_errors])
        if self.skipped_lines:
            lines.extend(["", "Diagnostics:", *self.skipped_lines])
        return "\n".join(lines) + "\n"


class ImportValidationError(RuntimeError):
    def __init__(self, report: ImportReport):
        super().__init__("content import validation failed")
        self.report = report


@dataclass
class ImportedContent:
    vocabulary: OrderedDict[str, list[str]]
    forms_only_words: set[str]
    forms: OrderedDict[str, list[GeneratedForm]]
    sentences: OrderedDict[str, list[str]]
    frequency_words: OrderedDict[str, int]
    recommendation_lemmas: dict[str, str]
    report: ImportReport


def _read_lines(path: Path):
    return [] if not path.exists() else enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)


def _parse_line(path: Path, line_number: int, line: str, report: ImportReport) -> tuple[str, list[str]] | None:
    if not line.strip() or line.startswith("#"):
        return None
    if line.count(" - ") != 1:
        report.skipped_lines.append(f"{path}: line {line_number}: expected exactly one ' - ' separator")
        return None
    left, right = line.split(" - ")
    values = [value.strip() for value in right.split(" / ")]
    if not left.strip() or not right.strip() or any(not value for value in values):
        report.skipped_lines.append(f"{path}: line {line_number}: empty field")
        return None
    return left.strip(), values


def _recommendation_surfaces(vocabulary: OrderedDict[str, list[str]], forms: OrderedDict[str, list[GeneratedForm]], sentences: OrderedDict[str, list[str]], frequency_words: OrderedDict[str, int]) -> set[str]:
    known: set[str] = set()
    for word in vocabulary:
        word_tokens = tokens(word)
        if len(word_tokens) == 1 and next(iter(word_tokens)) == word.casefold():
            known.update(word_tokens)
    for form_cards in forms.values():
        for form_card in form_cards:
            form_tokens = tokens(form_card.form)
            if len(form_tokens) == 1 and next(iter(form_tokens)) == form_card.form.casefold():
                known.update(form_tokens)
    candidates: set[str] = set()
    for sentence in sentences:
        sentence_tokens = tokens(sentence)
        if sentence_tokens.intersection(known):
            candidates.update(token for token in sentence_tokens if len(token) >= 3 and token not in known and token in frequency_words)
    ranks = {token: rank for rank, token in enumerate(frequency_words, start=1)}
    return set(sorted(candidates, key=ranks.__getitem__)[:RECOMMENDATION_LEMMA_CANDIDATE_LIMIT])


def parse_content(project_root: Path) -> ImportedContent:
    report = ImportReport()
    vocabulary: OrderedDict[str, list[str]] = OrderedDict()
    sentences: OrderedDict[str, list[str]] = OrderedDict()
    frequency_words: OrderedDict[str, int] = OrderedDict()
    dictionary_path = project_root / "dictionary.txt"
    report.dictionary_file_count = int(dictionary_path.exists())
    for number, line in _read_lines(dictionary_path):
        parsed = _parse_line(dictionary_path, number, line, report)
        if parsed is None:
            continue
        finnish, meanings = parsed
        if finnish in vocabulary:
            report.duplicate_vocabulary_count += 1
            report.skipped_lines.append(f"{dictionary_path}: line {number}: duplicate vocabulary '{finnish}'")
            continue
        vocabulary[finnish] = list(OrderedDict.fromkeys(meanings))

    forms_only_words = {
        word for word, meanings in vocabulary.items()
        if word[:1].isupper() and all(meaning == word for meaning in meanings)
    }

    source_path = project_root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
    index_path = project_root / "data" / "kaikki-forms.sqlite"
    if not source_path.exists() and not index_path.exists():
        report.fatal_errors.append(f"missing Kaikki source and index: {source_path}")
    elif source_path.exists():
        index_path.parent.mkdir(parents=True, exist_ok=True)
        report.kaikki_index_rebuilt = ensure_index(source_path, index_path, set(vocabulary))

    forms: OrderedDict[str, list[GeneratedForm]] = OrderedDict()
    if index_path.exists():
        for word in vocabulary:
            generated, alternatives = generated_forms(index_path, word)
            forms[word] = generated
            if not generated:
                report.missing_lexicon_profiles.append(word)
            if alternatives:
                report.form_alternatives[word] = alternatives
    else:
        forms = OrderedDict((word, []) for word in vocabulary)

    frequency_path = project_root / "frequency" / "fi_50k.txt"
    report.frequency_file_count = int(frequency_path.exists())
    if not frequency_path.exists():
        report.fatal_errors.append(f"missing required frequency file: {frequency_path}")
    else:
        for number, line in _read_lines(frequency_path):
            fields = line.split()
            if len(fields) != 2:
                report.fatal_errors.append(f"{frequency_path}: line {number}: expected word and positive frequency count")
                continue
            word, count_text = fields
            try:
                count = int(count_text)
            except ValueError:
                report.fatal_errors.append(f"{frequency_path}: line {number}: invalid frequency count '{count_text}'")
                continue
            if count <= 0:
                report.fatal_errors.append(f"{frequency_path}: line {number}: frequency count must be positive")
                continue
            token = word.casefold()
            if token in frequency_words:
                report.fatal_errors.append(f"{frequency_path}: line {number}: duplicate frequency word '{word}'")
                continue
            frequency_words[token] = count

    sentences_dir = project_root / "sentences"
    sentence_paths = sorted(sentences_dir.glob("*.txt")) if sentences_dir.exists() else []
    report.sentence_file_count = len(sentence_paths)
    for sentence_path in sentence_paths:
        for number, line in _read_lines(sentence_path):
            parsed = _parse_line(sentence_path, number, line, report)
            if parsed is None:
                continue
            finnish, translations = parsed
            if finnish in sentences:
                report.duplicate_sentence_count += 1
            else:
                sentences[finnish] = []
            for translation in translations:
                if translation in sentences[finnish]:
                    report.duplicate_translation_count += 1
                else:
                    sentences[finnish].append(translation)

    recommendation_index_path = project_root / "data" / "kaikki-recommendations.sqlite"
    recommendation_surfaces = _recommendation_surfaces(vocabulary, forms, sentences, frequency_words)
    lemma_mappings: dict[str, str] = {}
    if source_path.exists():
        report.recommendation_lemma_index_rebuilt = ensure_recommendation_index(source_path, recommendation_index_path, recommendation_surfaces)
    lemma_mappings = recommendation_lemmas(recommendation_index_path)

    report.vocabulary_count = len(vocabulary)
    report.form_count = sum(len(entries) for entries in forms.values())
    report.sentence_count = len(sentences)
    report.translation_count = sum(len(translations) for translations in sentences.values())
    report.frequency_entry_count = len(frequency_words)
    report.content_health = analyze_content_health(
        vocabulary,
        ((base_word, form.form, form.prompt_label) for base_word, entries in forms.items() for form in entries),
        sentences,
    )
    return ImportedContent(vocabulary, forms_only_words, forms, sentences, frequency_words, lemma_mappings, report)


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE vocabulary (id INTEGER PRIMARY KEY, finnish TEXT NOT NULL UNIQUE, meaning_quizzable INTEGER NOT NULL CHECK (meaning_quizzable IN (0, 1)));
CREATE TABLE vocabulary_meanings (vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE, meaning TEXT NOT NULL, ordinal INTEGER NOT NULL, PRIMARY KEY (vocabulary_id, meaning));
CREATE INDEX idx_vocabulary_meanings_vocab ON vocabulary_meanings(vocabulary_id);
CREATE TABLE word_forms (id INTEGER PRIMARY KEY, vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE, card_key TEXT NOT NULL, form TEXT NOT NULL, profile TEXT NOT NULL, prompt_label TEXT NOT NULL, UNIQUE (vocabulary_id, card_key));
CREATE INDEX idx_word_forms_vocab ON word_forms(vocabulary_id);
CREATE TABLE sentences (id INTEGER PRIMARY KEY, finnish TEXT NOT NULL UNIQUE);
CREATE TABLE sentence_translations (sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE, english TEXT NOT NULL, ordinal INTEGER NOT NULL, PRIMARY KEY (sentence_id, english));
CREATE INDEX idx_sentence_translations_sentence ON sentence_translations(sentence_id);
CREATE TABLE sentence_tokens (token_casefold TEXT NOT NULL, sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE, PRIMARY KEY (token_casefold, sentence_id));
CREATE TABLE frequency_words (token_casefold TEXT PRIMARY KEY, frequency_rank INTEGER NOT NULL UNIQUE, frequency_count INTEGER NOT NULL CHECK (frequency_count > 0));
CREATE TABLE recommendation_lemmas (surface TEXT PRIMARY KEY, lemma TEXT NOT NULL);
CREATE TABLE content_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _build_database(path: Path, content: ImportedContent, revision: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        with connection:
            for word, meanings in content.vocabulary.items():
                vocabulary_id = connection.execute(
                    "INSERT INTO vocabulary (finnish, meaning_quizzable) VALUES (?, ?)",
                    (word, int(word not in content.forms_only_words)),
                ).lastrowid
                connection.executemany("INSERT INTO vocabulary_meanings (vocabulary_id, meaning, ordinal) VALUES (?, ?, ?)", [(vocabulary_id, meaning, ordinal) for ordinal, meaning in enumerate(meanings)])
                connection.executemany("INSERT INTO word_forms (vocabulary_id, card_key, form, profile, prompt_label) VALUES (?, ?, ?, ?, ?)", [(vocabulary_id, form.card_key, form.form, form.profile, form.prompt_label) for form in content.forms[word]])
            connection.executemany("INSERT INTO sentences (finnish) VALUES (?)", ((finnish,) for finnish in content.sentences))
            sentence_ids = {finnish: sentence_id for sentence_id, finnish in connection.execute("SELECT id, finnish FROM sentences")}
            connection.executemany("INSERT INTO sentence_translations (sentence_id, english, ordinal) VALUES (?, ?, ?)", ((sentence_ids[finnish], english, ordinal) for finnish, translations in content.sentences.items() for ordinal, english in enumerate(translations)))
            connection.executemany("INSERT INTO sentence_tokens (token_casefold, sentence_id) VALUES (?, ?)", ((token, sentence_ids[finnish]) for finnish in content.sentences for token in tokens(finnish)))
            connection.executemany("INSERT INTO frequency_words (token_casefold, frequency_rank, frequency_count) VALUES (?, ?, ?)", ((token, rank, count) for rank, (token, count) in enumerate(content.frequency_words.items(), start=1)))
            connection.executemany("INSERT INTO recommendation_lemmas (surface, lemma) VALUES (?, ?)", content.recommendation_lemmas.items())
            connection.execute("INSERT INTO content_metadata (key, value) VALUES ('revision', ?)", (revision,))
            connection.execute("CREATE INDEX idx_sentence_tokens_sentence ON sentence_tokens(sentence_id)")
        if connection.execute("PRAGMA foreign_key_check").fetchall() or connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("content database integrity verification failed")


def run_import(project_root: Path = PROJECT_ROOT, *, dry_run: bool = False) -> ImportReport:
    content = parse_content(project_root)
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_path = data_dir / "import-report.txt"
    if content.report.fatal_errors:
        report_path.write_text(content.report.render(dry_run=dry_run), encoding="utf-8")
        raise ImportValidationError(content.report)
    if not dry_run:
        descriptor, temporary_name = tempfile.mkstemp(prefix="content-", suffix=".sqlite", dir=data_dir)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            _build_database(temporary_path, content, uuid.uuid4().hex)
            os.replace(temporary_path, data_dir / "content.sqlite")
        finally:
            temporary_path.unlink(missing_ok=True)
    report_path.write_text(content.report.render(dry_run=dry_run), encoding="utf-8")
    return content.report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ToistoKone content database")
    parser.add_argument("--dry-run", action="store_true", help="write only the import report")
    arguments = parser.parse_args()
    try:
        report = run_import(dry_run=arguments.dry_run)
    except ImportValidationError as error:
        print(error.report.render(dry_run=arguments.dry_run), end="")
        print("Import failed: content validation errors found.", file=sys.stderr)
        raise SystemExit(1) from error
    print(report.render(dry_run=arguments.dry_run), end="")


if __name__ == "__main__":
    main()
