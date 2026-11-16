from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.config import PROJECT_ROOT
from backend.app.sentences import tokens


@dataclass
class ImportReport:
    dictionary_file_count: int = 0
    word_forms_file_count: int = 0
    sentence_file_count: int = 0
    vocabulary_count: int = 0
    form_count: int = 0
    sentence_count: int = 0
    translation_count: int = 0
    duplicate_vocabulary_count: int = 0
    duplicate_form_count: int = 0
    duplicate_sentence_count: int = 0
    duplicate_translation_count: int = 0
    skipped_lines: list[str] = field(default_factory=list)

    def render(self, *, dry_run: bool) -> str:
        lines = [
            "ToistoKone import report",
            f"Mode: {'dry run' if dry_run else 'normal'}",
            f"Dictionary files: {self.dictionary_file_count}",
            f"Word-form files: {self.word_forms_file_count}",
            f"Sentence files: {self.sentence_file_count}",
            f"Imported vocabulary: {self.vocabulary_count}",
            f"Imported word forms: {self.form_count}",
            f"Imported sentences: {self.sentence_count}",
            f"Imported translations: {self.translation_count}",
            f"Duplicate vocabulary entries: {self.duplicate_vocabulary_count}",
            f"Duplicate word forms: {self.duplicate_form_count}",
            f"Duplicate sentences: {self.duplicate_sentence_count}",
            f"Duplicate translations: {self.duplicate_translation_count}",
            f"Skipped lines: {len(self.skipped_lines)}",
        ]
        if self.skipped_lines:
            lines.extend(["", "Diagnostics:", *self.skipped_lines])
        return "\n".join(lines) + "\n"


@dataclass
class ImportedContent:
    vocabulary: OrderedDict[str, list[str]]
    forms: OrderedDict[str, OrderedDict[str, str | None]]
    sentences: OrderedDict[str, list[str]]
    report: ImportReport


def _read_lines(path: Path):
    if not path.exists():
        return []
    return enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)


def _parse_line(path: Path, line_number: int, line: str, report: ImportReport) -> tuple[str, list[str]] | None:
    if not line.strip() or line.startswith("#"):
        return None
    if line.count(" - ") != 1:
        report.skipped_lines.append(f"{path}: line {line_number}: expected exactly one ' - ' separator")
        return None
    left, right = line.split(" - ")
    left = left.strip()
    values = [value.strip() for value in right.split(" / ")]
    if not left or not right.strip() or any(not value for value in values):
        report.skipped_lines.append(f"{path}: line {line_number}: empty field")
        return None
    return left, values


def parse_content(project_root: Path) -> ImportedContent:
    report = ImportReport()
    vocabulary: OrderedDict[str, list[str]] = OrderedDict()
    forms: OrderedDict[str, OrderedDict[str, str | None]] = OrderedDict()
    sentences: OrderedDict[str, list[str]] = OrderedDict()

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

    raw_edges: list[tuple[Path, int, str, str]] = []
    forms_path = project_root / "word-forms.txt"
    report.word_forms_file_count = int(forms_path.exists())
    for number, line in _read_lines(forms_path):
        parsed = _parse_line(forms_path, number, line, report)
        if parsed is None:
            continue
        parent, children = parsed
        for child in children:
            raw_edges.append((forms_path, number, parent, child))

    parent_by_child: OrderedDict[str, tuple[str, Path, int]] = OrderedDict()
    for path, line_number, parent, child in raw_edges:
        if child in vocabulary or child in parent_by_child:
            report.duplicate_form_count += 1
            report.skipped_lines.append(f"{path}: line {line_number}: duplicate or ambiguous form '{child}'")
            continue
        parent_by_child[child] = (parent, path, line_number)

    resolving: set[str] = set()
    resolved_roots: dict[str, str | None] = {}

    def resolve_root(form: str) -> str | None:
        if form in vocabulary:
            return form
        if form in resolved_roots:
            return resolved_roots[form]
        if form in resolving or form not in parent_by_child:
            return None
        resolving.add(form)
        parent, _, _ = parent_by_child[form]
        root = resolve_root(parent)
        resolving.remove(form)
        resolved_roots[form] = root
        return root

    forms = OrderedDict((word, OrderedDict([(word, None)])) for word in vocabulary)
    for child, (parent, path, line_number) in parent_by_child.items():
        if resolve_root(child) is None:
            report.skipped_lines.append(f"{path}: line {line_number}: unknown parent or cycle for form '{child}'")

    def add_form(root: str, form: str) -> None:
        if form in forms[root] or form not in parent_by_child:
            return
        parent, _, _ = parent_by_child[form]
        if parent != root:
            add_form(root, parent)
        forms[root][form] = parent

    for child, root in resolved_roots.items():
        if root is not None:
            add_form(root, child)

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
                    continue
                sentences[finnish].append(translation)

    report.vocabulary_count = len(vocabulary)
    report.form_count = sum(len(word_forms) for word_forms in forms.values())
    report.sentence_count = len(sentences)
    report.translation_count = sum(len(translations) for translations in sentences.values())
    return ImportedContent(vocabulary, forms, sentences, report)


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE vocabulary (id INTEGER PRIMARY KEY, finnish TEXT NOT NULL UNIQUE);
CREATE TABLE vocabulary_meanings (
    vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
    meaning TEXT NOT NULL, ordinal INTEGER NOT NULL,
    PRIMARY KEY (vocabulary_id, meaning)
);
CREATE INDEX idx_vocabulary_meanings_vocab ON vocabulary_meanings(vocabulary_id);
CREATE TABLE word_forms (
    id INTEGER PRIMARY KEY,
    vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
    form TEXT NOT NULL,
    parent_form TEXT,
    FOREIGN KEY (vocabulary_id, parent_form) REFERENCES word_forms(vocabulary_id, form),
    UNIQUE (vocabulary_id, form)
);
CREATE INDEX idx_word_forms_vocab ON word_forms(vocabulary_id);
CREATE TABLE sentences (id INTEGER PRIMARY KEY, finnish TEXT NOT NULL UNIQUE);
CREATE TABLE sentence_translations (
    sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    english TEXT NOT NULL, ordinal INTEGER NOT NULL,
    PRIMARY KEY (sentence_id, english)
);
CREATE INDEX idx_sentence_translations_sentence ON sentence_translations(sentence_id);
CREATE TABLE sentence_tokens (
    token_casefold TEXT NOT NULL,
    sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    PRIMARY KEY (token_casefold, sentence_id)
);
"""


def _build_database(path: Path, content: ImportedContent) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        with connection:
            for word, meanings in content.vocabulary.items():
                cursor = connection.execute("INSERT INTO vocabulary (finnish) VALUES (?)", (word,))
                vocabulary_id = cursor.lastrowid
                connection.executemany(
                    "INSERT INTO vocabulary_meanings (vocabulary_id, meaning, ordinal) VALUES (?, ?, ?)",
                    [(vocabulary_id, meaning, ordinal) for ordinal, meaning in enumerate(meanings)],
                )
                connection.executemany(
                    "INSERT INTO word_forms (vocabulary_id, form, parent_form) VALUES (?, ?, ?)",
                    [(vocabulary_id, form, parent) for form, parent in content.forms[word].items()],
                )
            for finnish, translations in content.sentences.items():
                cursor = connection.execute("INSERT INTO sentences (finnish) VALUES (?)", (finnish,))
                sentence_id = cursor.lastrowid
                connection.executemany(
                    "INSERT INTO sentence_translations (sentence_id, english, ordinal) VALUES (?, ?, ?)",
                    [(sentence_id, english, ordinal) for ordinal, english in enumerate(translations)],
                )
                connection.executemany(
                    "INSERT INTO sentence_tokens (token_casefold, sentence_id) VALUES (?, ?)",
                    [(token, sentence_id) for token in tokens(finnish)],
                )
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if foreign_key_errors or integrity != "ok":
            raise RuntimeError("content database integrity verification failed")
    finally:
        connection.close()


def run_import(project_root: Path = PROJECT_ROOT, *, dry_run: bool = False) -> ImportReport:
    content = parse_content(project_root)
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_path = data_dir / "import-report.txt"
    if not dry_run:
        descriptor, temporary_name = tempfile.mkstemp(prefix="content-", suffix=".sqlite", dir=data_dir)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            _build_database(temporary_path, content)
            os.replace(temporary_path, data_dir / "content.sqlite")
        finally:
            temporary_path.unlink(missing_ok=True)
    report_path.write_text(content.report.render(dry_run=dry_run), encoding="utf-8")
    return content.report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ToistoKone content database")
    parser.add_argument("--dry-run", action="store_true", help="write only the import report")
    arguments = parser.parse_args()
    report = run_import(dry_run=arguments.dry_run)
    print(report.render(dry_run=arguments.dry_run), end="")


if __name__ == "__main__":
    main()
