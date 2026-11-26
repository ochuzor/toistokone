from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from backend.app.config import PROJECT_ROOT
from backend.app.content_health import ContentHealth, analyze_content_health
from backend.app.sentences import tokens
from backend.kaikki import GeneratedForm, ensure_index, ensure_recommendation_index, generated_forms, recommendation_lemmas


RECOMMENDATION_LEMMA_CANDIDATE_LIMIT = 100
MINIMUM_LEARNING_SET_WORDS = 10
LEARNING_SET_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ProgressReporter = Callable[[str], None]


@dataclass
class ImportReport:
    dictionary_file_count: int = 0
    frequency_file_count: int = 0
    sentence_file_count: int = 0
    learning_set_file_count: int = 0
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
    learning_set_coverage: list["LearningSetCoverage"] = field(default_factory=list)
    fatal_errors: list[str] = field(default_factory=list)
    skipped_lines: list[str] = field(default_factory=list)

    def render(self, *, dry_run: bool) -> str:
        lines = [
            "# ToistoKone import report", "",
            f"**Mode:** {'dry run' if dry_run else 'normal'}", "",
            "## Import summary",
            f"- Dictionary files: {self.dictionary_file_count}", f"- Frequency files: {self.frequency_file_count}",
            f"- Sentence files: {self.sentence_file_count}", f"- Kaikki index rebuilt: {'yes' if self.kaikki_index_rebuilt else 'no'}",
            f"- Learning-set files: {self.learning_set_file_count}",
            f"- Recommendation lemma index rebuilt: {'yes' if self.recommendation_lemma_index_rebuilt else 'no'}",
            f"- Imported vocabulary: {self.vocabulary_count}", f"- Imported grammar forms: {self.form_count}",
            f"- Imported sentences: {self.sentence_count}", f"- Imported translations: {self.translation_count}",
            f"- Imported frequency entries: {self.frequency_entry_count}",
            f"- Duplicate vocabulary entries: {self.duplicate_vocabulary_count}",
            f"- Duplicate sentences: {self.duplicate_sentence_count}",
            f"- Duplicate translations: {self.duplicate_translation_count}",
            f"- Words without usable Kaikki profiles: {len(self.missing_lexicon_profiles)}",
            f"- Form slots with alternatives: {sum(len(slots) for slots in self.form_alternatives.values())}",
            f"- Errors: {len(self.fatal_errors)}", f"- Skipped lines: {len(self.skipped_lines)}",
        ]
        if self.content_health:
            summary = self.content_health.summary()
            lines.extend([
                "", "## Content health",
                f"- Words without usable Kaikki profiles: {summary['missing_profiles']}",
                f"- Base words without supporting sentences: {summary['base_without_sentences']}",
                f"- Form cards with fewer than two supporting sentences: {summary['under_supported_forms']}",
                f"- Sentences without tracked vocabulary or forms: {summary['untracked_sentences']}",
            ])
        if self.learning_set_coverage:
            lines.extend(["", "## Learning-set coverage"])
            lines.extend(
                f"- {coverage.title}: {coverage.word_count} words, {coverage.form_count} forms; "
                f"{coverage.words_without_sentences} words without sentences, "
                f"{coverage.forms_with_fewer_than_two_sentences} forms with fewer than two sentences"
                for coverage in self.learning_set_coverage
            )
        if self.form_alternatives:
            lines.extend(["", "## Alternative Kaikki forms (first candidate selected)"])
            for word in sorted(self.form_alternatives):
                lines.append(f"- {word}:")
                for slot, alternatives in sorted(self.form_alternatives[word].items()):
                    lines.append(f"  - {slot}: {' / '.join(alternatives)}")
        if self.content_health:
            if self.content_health.missing_profiles:
                lines.extend([
                    "", "## Words without usable Kaikki profiles",
                    *[f"- {finding.word} — {finding.priority_reason}" for finding in self.content_health.missing_profiles],
                ])
            if self.content_health.base_without_sentences:
                lines.extend([
                    "", "## Base words without supporting sentences",
                    *[f"- {finding.word} — {finding.priority_reason}" for finding in self.content_health.base_without_sentences],
                ])
            if self.content_health.under_supported_forms:
                lines.extend([
                    "", "## Form cards with fewer than two supporting sentences",
                    *[
                        f"- {finding.base_word} → {finding.form}: {finding.prompt_label} "
                        f"({finding.sentence_count}) — {finding.priority_reason}"
                        for finding in self.content_health.under_supported_forms
                    ],
                ])
            if self.content_health.untracked_sentences:
                lines.extend([
                    "", "## Sentences without tracked vocabulary or forms",
                    *[f"- {finding.finnish} — {finding.priority_reason}" for finding in self.content_health.untracked_sentences],
                ])
        if self.fatal_errors:
            lines.extend(["", "## Errors", *[f"- {error}" for error in self.fatal_errors]])
        if self.skipped_lines:
            lines.extend(["", "## Diagnostics", *[f"- {line}" for line in self.skipped_lines]])
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
    learning_sets: list["LearningSet"]
    report: ImportReport


@dataclass(frozen=True)
class LearningSet:
    key: str
    title: str
    words: tuple[str, ...]


@dataclass(frozen=True)
class LearningSetCoverage:
    title: str
    word_count: int
    form_count: int
    words_without_sentences: int
    forms_with_fewer_than_two_sentences: int


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


def _parse_learning_sets(root: Path, vocabulary: OrderedDict[str, list[str]], report: ImportReport) -> list[LearningSet]:
    directory = root / "learning-sets"
    paths = sorted(directory.glob("*.md")) if directory.exists() else []
    report.learning_set_file_count = len(paths)
    learning_sets: list[LearningSet] = []
    known_ids: dict[str, tuple[Path, int]] = {}
    for path in paths:
        lines = list(_read_lines(path))
        key: str | None = None
        key_line: int | None = None
        title: str | None = None
        words: list[str] = []
        seen: set[str] = set()
        position = 0
        if not lines or lines[0][1].strip() != "---":
            report.fatal_errors.append(f"{path}: line 1: expected opening '---' for learning-set ID")
        else:
            position = 1
            closed = False
            while position < len(lines):
                number, raw_line = lines[position]
                line = raw_line.strip()
                position += 1
                if not line:
                    continue
                if line == "---":
                    closed = True
                    break
                if line.startswith("id: ") and line[4:].strip():
                    if key is not None:
                        report.fatal_errors.append(f"{path}: line {number}: duplicate learning-set ID")
                    else:
                        key = line[4:].strip()
                        key_line = number
                else:
                    report.fatal_errors.append(f"{path}: line {number}: expected 'id: lower-case-kebab-id'")
            if not closed:
                report.fatal_errors.append(f"{path}: missing closing '---' for learning-set ID")
            elif key is None:
                report.fatal_errors.append(f"{path}: missing learning-set ID")
            elif not LEARNING_SET_ID_PATTERN.fullmatch(key):
                report.fatal_errors.append(f"{path}: line {key_line}: learning-set ID '{key}' must use lower-case kebab-case")
            elif key in known_ids:
                previous_path, previous_line = known_ids[key]
                report.fatal_errors.append(
                    f"{path}: line {key_line}: learning-set ID '{key}' conflicts with {previous_path}: line {previous_line}"
                )
            else:
                known_ids[key] = (path, key_line)
        for number, raw_line in lines[position:]:
            line = raw_line.strip()
            if not line:
                continue
            if title is None:
                if not line.startswith("# ") or not line[2:].strip():
                    report.fatal_errors.append(f"{path}: line {number}: expected a '# Title' heading")
                    break
                title = line[2:].strip()
                continue
            if not line.startswith("- ") or not line[2:].strip():
                report.fatal_errors.append(f"{path}: line {number}: expected a '- dictionary word' entry")
                continue
            word = line[2:].strip()
            if word in seen:
                report.fatal_errors.append(f"{path}: line {number}: duplicate learning-set word '{word}'")
            elif word not in vocabulary:
                report.fatal_errors.append(f"{path}: line {number}: unknown dictionary word '{word}'")
            else:
                seen.add(word)
                words.append(word)
        if title is None:
            report.fatal_errors.append(f"{path}: expected a '# Title' heading")
        elif len(words) < MINIMUM_LEARNING_SET_WORDS:
            report.fatal_errors.append(
                f"{path}: learning set must contain at least {MINIMUM_LEARNING_SET_WORDS} dictionary words (found {len(words)})"
            )
        elif key is not None and LEARNING_SET_ID_PATTERN.fullmatch(key) and known_ids.get(key, (None, None))[0] == path:
            learning_sets.append(LearningSet(key, title, tuple(words)))
    return learning_sets


def _learning_set_coverage(
    learning_sets: list[LearningSet], forms: OrderedDict[str, list[GeneratedForm]], sentences: OrderedDict[str, list[str]]
) -> list[LearningSetCoverage]:
    sentence_tokens = {sentence: tokens(sentence) for sentence in sentences}

    def support(surface: str) -> int:
        surface_tokens = tokens(surface)
        if len(surface_tokens) != 1 or next(iter(surface_tokens)) != surface.casefold():
            return 0
        return sum(surface.casefold() in token_set for token_set in sentence_tokens.values())

    return [
        LearningSetCoverage(
            learning_set.title,
            len(learning_set.words),
            sum(len(forms[word]) for word in learning_set.words),
            sum(support(word) == 0 for word in learning_set.words),
            sum(support(form.form) < 2 for word in learning_set.words for form in forms[word]),
        )
        for learning_set in learning_sets
    ]


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


def parse_content(project_root: Path, *, progress: ProgressReporter | None = None) -> ImportedContent:
    report = ImportReport()
    vocabulary: OrderedDict[str, list[str]] = OrderedDict()
    sentences: OrderedDict[str, list[str]] = OrderedDict()
    frequency_words: OrderedDict[str, int] = OrderedDict()
    dictionary_path = project_root / "dictionary.txt"
    report.dictionary_file_count = int(dictionary_path.exists())
    if progress:
        progress("Reading dictionary")
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
    if progress:
        progress(f"Dictionary: {len(vocabulary):,} entries")

    if progress:
        progress("Reading learning sets")
    learning_sets = _parse_learning_sets(project_root, vocabulary, report)

    forms_only_words = {
        word for word, meanings in vocabulary.items()
        if word[:1].isupper() and all(meaning == word for meaning in meanings)
    }

    source_path = project_root / "lexicon" / "kaikki.org-dictionary-Finnish-words.jsonl"
    index_path = project_root / "data" / "kaikki-forms.sqlite"
    if not source_path.exists() and not index_path.exists():
        report.fatal_errors.append(f"missing Kaikki source and index: {source_path}")

    frequency_path = project_root / "frequency" / "fi_50k.txt"
    report.frequency_file_count = int(frequency_path.exists())
    if progress:
        progress("Reading frequency list")
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
    if progress:
        progress(f"Frequency list: {len(frequency_words):,} entries")

    report.vocabulary_count = len(vocabulary)
    report.frequency_entry_count = len(frequency_words)
    if report.fatal_errors:
        return ImportedContent(
            vocabulary, forms_only_words, OrderedDict((word, []) for word in vocabulary),
            sentences, frequency_words, {}, learning_sets, report,
        )

    if source_path.exists():
        index_path.parent.mkdir(parents=True, exist_ok=True)
        report.kaikki_index_rebuilt = ensure_index(source_path, index_path, set(vocabulary), progress=progress)

    forms: OrderedDict[str, list[GeneratedForm]] = OrderedDict()
    if index_path.exists():
        if progress:
            progress("Loading generated grammar forms")
        for word in vocabulary:
            generated, alternatives = generated_forms(index_path, word)
            forms[word] = generated
            if not generated:
                report.missing_lexicon_profiles.append(word)
            if alternatives:
                report.form_alternatives[word] = alternatives
    else:
        forms = OrderedDict((word, []) for word in vocabulary)

    sentences_dir = project_root / "sentences"
    sentence_paths = sorted(sentences_dir.glob("*.txt")) if sentences_dir.exists() else []
    report.sentence_file_count = len(sentence_paths)
    for file_number, sentence_path in enumerate(sentence_paths, start=1):
        if progress:
            progress(f"Reading sentences ({file_number}/{len(sentence_paths)}): {sentence_path.name}")
        for number, line in _read_lines(sentence_path):
            if progress and number % 10_000 == 0:
                progress(f"Reading sentences ({file_number}/{len(sentence_paths)}): {sentence_path.name} — {number:,} lines")
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
    if progress:
        progress(f"Sentences: {len(sentences):,} unique")

    recommendation_index_path = project_root / "data" / "kaikki-recommendations.sqlite"
    recommendation_surfaces = _recommendation_surfaces(vocabulary, forms, sentences, frequency_words)
    lemma_mappings: dict[str, str] = {}
    if source_path.exists():
        report.recommendation_lemma_index_rebuilt = ensure_recommendation_index(source_path, recommendation_index_path, recommendation_surfaces, progress=progress)
    lemma_mappings = recommendation_lemmas(recommendation_index_path)

    report.vocabulary_count = len(vocabulary)
    report.form_count = sum(len(entries) for entries in forms.values())
    report.sentence_count = len(sentences)
    report.translation_count = sum(len(translations) for translations in sentences.values())
    report.frequency_entry_count = len(frequency_words)
    report.learning_set_coverage = _learning_set_coverage(learning_sets, forms, sentences)
    if progress:
        progress("Analyzing content health")
    report.content_health = analyze_content_health(
        vocabulary,
        ((base_word, form.form, form.prompt_label) for base_word, entries in forms.items() for form in entries),
        sentences,
        progress_path=project_root / "data" / "progress.sqlite",
        frequency_ranks={token: rank for rank, token in enumerate(frequency_words, start=1)},
    )
    return ImportedContent(vocabulary, forms_only_words, forms, sentences, frequency_words, lemma_mappings, learning_sets, report)


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE vocabulary (id INTEGER PRIMARY KEY, finnish TEXT NOT NULL UNIQUE, meaning_quizzable INTEGER NOT NULL CHECK (meaning_quizzable IN (0, 1)));
CREATE TABLE vocabulary_meanings (vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE, meaning TEXT NOT NULL, ordinal INTEGER NOT NULL, PRIMARY KEY (vocabulary_id, meaning));
CREATE INDEX idx_vocabulary_meanings_vocab ON vocabulary_meanings(vocabulary_id);
CREATE TABLE word_forms (id INTEGER PRIMARY KEY, vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE, card_key TEXT NOT NULL, form TEXT NOT NULL, profile TEXT NOT NULL, prompt_label TEXT NOT NULL, UNIQUE (vocabulary_id, card_key));
CREATE INDEX idx_word_forms_vocab ON word_forms(vocabulary_id);
CREATE TABLE learning_sets (key TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE learning_set_words (set_key TEXT NOT NULL REFERENCES learning_sets(key) ON DELETE CASCADE, vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE, PRIMARY KEY (set_key, vocabulary_id));
CREATE INDEX idx_learning_set_words_vocab ON learning_set_words(vocabulary_id);
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
            vocabulary_ids = {word: vocabulary_id for word, vocabulary_id in connection.execute("SELECT finnish, id FROM vocabulary")}
            connection.executemany("INSERT INTO learning_sets (key, title) VALUES (?, ?)", [(learning_set.key, learning_set.title) for learning_set in content.learning_sets])
            connection.executemany(
                "INSERT INTO learning_set_words (set_key, vocabulary_id) VALUES (?, ?)",
                [(learning_set.key, vocabulary_ids[word]) for learning_set in content.learning_sets for word in learning_set.words],
            )
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


def run_import(project_root: Path = PROJECT_ROOT, *, dry_run: bool = False, progress: ProgressReporter | None = None) -> ImportReport:
    content = parse_content(project_root, progress=progress)
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_path = data_dir / "import-report.md"
    if content.report.fatal_errors:
        if progress:
            progress("Writing import report")
        report_path.write_text(content.report.render(dry_run=dry_run), encoding="utf-8")
        raise ImportValidationError(content.report)
    if not dry_run:
        if progress:
            progress("Building content database")
        descriptor, temporary_name = tempfile.mkstemp(prefix="content-", suffix=".sqlite", dir=data_dir)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            _build_database(temporary_path, content, uuid.uuid4().hex)
            os.replace(temporary_path, data_dir / "content.sqlite")
        finally:
            temporary_path.unlink(missing_ok=True)
        if progress:
            progress("Content database: complete")
    elif progress:
        progress("Dry run: skipping content database build")
    if progress:
        progress("Writing import report")
    report_path.write_text(content.report.render(dry_run=dry_run), encoding="utf-8")
    return content.report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ToistoKone content database")
    parser.add_argument("--dry-run", action="store_true", help="write only the import report")
    arguments = parser.parse_args()
    try:
        report = run_import(dry_run=arguments.dry_run, progress=lambda message: print(message, file=sys.stderr, flush=True))
    except ImportValidationError as error:
        print("Import failed: content validation errors found. See data/import-report.md.", file=sys.stderr)
        raise SystemExit(1) from error
    print("Import complete. See data/import-report.md.")


if __name__ == "__main__":
    main()
