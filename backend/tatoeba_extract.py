from __future__ import annotations

import argparse
import os
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import PROJECT_ROOT
from backend.app.sentences import TOKEN_PATTERN


@dataclass
class ExtractionReport:
    frequency_entry_count: int = 0
    source_line_count: int = 0
    malformed_line_count: int = 0
    accepted_pair_count: int = 0
    rejected_too_long_count: int = 0
    rejected_too_rare_count: int = 0
    duplicate_sentence_count: int = 0
    duplicate_translation_count: int = 0
    sentence_count: int = 0
    translation_count: int = 0

    def render(self, *, max_tokens: int, top_rank: int, max_rare_tokens: int) -> str:
        return "\n".join(
            [
                "ToistoKone Tatoeba extraction report",
                f"Maximum Finnish word tokens: {max_tokens}",
                f"Common-word rank limit: {top_rank}",
                f"Maximum uncommon or missing tokens: {max_rare_tokens}",
                f"Frequency entries: {self.frequency_entry_count}",
                f"Source lines: {self.source_line_count}",
                f"Malformed source lines: {self.malformed_line_count}",
                f"Accepted sentence pairs: {self.accepted_pair_count}",
                f"Rejected for length: {self.rejected_too_long_count}",
                f"Rejected for uncommon tokens: {self.rejected_too_rare_count}",
                f"Duplicate Finnish sentences consolidated: {self.duplicate_sentence_count}",
                f"Duplicate translations consolidated: {self.duplicate_translation_count}",
                f"Output Finnish sentences: {self.sentence_count}",
                f"Output English translations: {self.translation_count}",
                "",
            ]
        )


def load_frequency_ranks(path: Path) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 2:
            raise ValueError(f"{path}: line {line_number}: expected a word and frequency count")
        word, count = fields
        try:
            int(count)
        except ValueError as error:
            raise ValueError(f"{path}: line {line_number}: invalid frequency count '{count}'") from error
        ranks.setdefault(word.casefold(), len(ranks) + 1)
    return ranks


def extract_sentences(
    frequency_path: Path,
    source_path: Path,
    *,
    max_tokens: int = 8,
    top_rank: int = 10_000,
    max_rare_tokens: int = 2,
) -> tuple[OrderedDict[str, list[str]], ExtractionReport]:
    ranks = load_frequency_ranks(frequency_path)
    report = ExtractionReport(frequency_entry_count=len(ranks))
    sentences: OrderedDict[str, list[str]] = OrderedDict()

    for line in source_path.read_text(encoding="utf-8").splitlines():
        report.source_line_count += 1
        if line.count(" - ") != 1:
            report.malformed_line_count += 1
            continue
        finnish, english = (value.strip() for value in line.split(" - "))
        if not finnish or not english:
            report.malformed_line_count += 1
            continue

        sentence_tokens = TOKEN_PATTERN.findall(finnish.casefold())
        if len(sentence_tokens) > max_tokens:
            report.rejected_too_long_count += 1
            continue
        rare_tokens = sum(ranks.get(token, top_rank + 1) > top_rank for token in sentence_tokens)
        if rare_tokens > max_rare_tokens:
            report.rejected_too_rare_count += 1
            continue

        report.accepted_pair_count += 1
        if finnish in sentences:
            report.duplicate_sentence_count += 1
        else:
            sentences[finnish] = []
        if english in sentences[finnish]:
            report.duplicate_translation_count += 1
            continue
        sentences[finnish].append(english)

    report.sentence_count = len(sentences)
    report.translation_count = sum(len(translations) for translations in sentences.values())
    return sentences, report


def _render_sentences(sentences: OrderedDict[str, list[str]]) -> str:
    return "".join(f"{finnish} - {' / '.join(translations)}\n" for finnish, translations in sentences.items())


def _write_new_file(path: Path, contents: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}; use --force to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(contents)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def run_extraction(
    frequency_path: Path,
    source_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    max_tokens: int = 8,
    top_rank: int = 10_000,
    max_rare_tokens: int = 2,
    force: bool = False,
) -> ExtractionReport:
    if not force:
        existing_paths = [path for path in (output_path, report_path) if path.exists()]
        if existing_paths:
            joined_paths = ", ".join(str(path) for path in existing_paths)
            raise FileExistsError(f"refusing to overwrite existing file(s): {joined_paths}; use --force to replace them")
    sentences, report = extract_sentences(
        frequency_path,
        source_path,
        max_tokens=max_tokens,
        top_rank=top_rank,
        max_rare_tokens=max_rare_tokens,
    )
    _write_new_file(output_path, _render_sentences(sentences), force=force)
    _write_new_file(
        report_path,
        report.render(max_tokens=max_tokens, top_rank=top_rank, max_rare_tokens=max_rare_tokens),
        force=force,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract beginner-friendly Finnish-English Tatoeba sentences")
    parser.add_argument("--frequency-file", type=Path, default=PROJECT_ROOT / "tatoeba" / "fi_50k.txt")
    parser.add_argument("--sentences-file", type=Path, default=PROJECT_ROOT / "tatoeba" / "finn-eng.txt")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "sentences" / "tatoeba-filtered.txt")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "tatoeba" / "extraction-report.txt")
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--top-rank", type=int, default=10_000)
    parser.add_argument("--max-rare-tokens", type=int, default=2)
    parser.add_argument("--force", action="store_true", help="replace existing output and report files")
    arguments = parser.parse_args()
    if arguments.max_tokens < 0 or arguments.top_rank < 1 or arguments.max_rare_tokens < 0:
        parser.error("filter limits must be non-negative, and --top-rank must be at least 1")
    try:
        report = run_extraction(
            arguments.frequency_file,
            arguments.sentences_file,
            arguments.output,
            arguments.report,
            max_tokens=arguments.max_tokens,
            top_rank=arguments.top_rank,
            max_rare_tokens=arguments.max_rare_tokens,
            force=arguments.force,
        )
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))
    print(report.render(
        max_tokens=arguments.max_tokens,
        top_rank=arguments.top_rank,
        max_rare_tokens=arguments.max_rare_tokens,
    ), end="")


if __name__ == "__main__":
    main()
