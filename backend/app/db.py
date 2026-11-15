from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import CardReference


PROGRESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS card_progress (
  card_type TEXT NOT NULL CHECK (card_type IN ('vocabulary', 'word_form')),
  base_word TEXT NOT NULL,
  target_form TEXT NOT NULL DEFAULT '',
  score INTEGER NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 3),
  last_practiced_at TEXT,
  last_score_increased_at TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  correct_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (card_type, base_word, target_form)
);
CREATE INDEX IF NOT EXISTS idx_card_progress_score_time ON card_progress(score, last_practiced_at);
CREATE TABLE IF NOT EXISTS practice_attempts (
  id INTEGER PRIMARY KEY,
  attempt_id TEXT NOT NULL UNIQUE,
  card_type TEXT NOT NULL,
  base_word TEXT NOT NULL,
  target_form TEXT NOT NULL DEFAULT '',
  correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
  score_before INTEGER NOT NULL,
  score_after INTEGER NOT NULL,
  answered_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_card ON practice_attempts(card_type, base_word, target_form, answered_at);
"""


def initialize_progress_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(PROGRESS_SCHEMA)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(card_progress)")}
        if "last_score_increased_at" not in columns:
            connection.execute("ALTER TABLE card_progress ADD COLUMN last_score_increased_at TEXT")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _score_after(score_before: int, correct: bool) -> int:
    if score_before == 3:
        return 3
    if correct:
        return min(score_before + 1, 3)
    return 1 if score_before == 2 else score_before


def _cooldown_active(last_score_increased_at: str | None, now: datetime, cooldown_minutes: int) -> bool:
    if not last_score_increased_at or cooldown_minutes == 0:
        return False
    increased_at = datetime.fromisoformat(last_score_increased_at)
    return now < increased_at + timedelta(minutes=cooldown_minutes)


def record_answer(
    path: Path,
    card: CardReference,
    attempt_id: str,
    correct: bool,
    cooldown_minutes: int,
    now: datetime | None = None,
) -> dict[str, int | bool]:
    now = now or _now()
    now_text = now.isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute(
            "SELECT correct, score_before, score_after FROM practice_attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        if previous:
            return {"correct": bool(previous[0]), "score_before": previous[1], "score_after": previous[2]}

        row = connection.execute(
            """SELECT score, last_score_increased_at FROM card_progress
               WHERE card_type = ? AND base_word = ? AND target_form = ?""",
            (card.type, card.base_word, card.target_form),
        ).fetchone()
        score_before = row[0] if row else 0
        score_after = score_before if _cooldown_active(row[1] if row else None, now, cooldown_minutes) else _score_after(score_before, correct)
        increased_at = now_text if score_after > score_before else None
        connection.execute(
            """INSERT INTO card_progress
               (card_type, base_word, target_form, score, last_practiced_at, last_score_increased_at, attempt_count, correct_count)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)
               ON CONFLICT(card_type, base_word, target_form) DO UPDATE SET
                 score = excluded.score,
                 last_practiced_at = excluded.last_practiced_at,
                 last_score_increased_at = CASE
                   WHEN excluded.score > card_progress.score THEN excluded.last_score_increased_at
                   ELSE card_progress.last_score_increased_at
                 END,
                 attempt_count = card_progress.attempt_count + 1,
                 correct_count = card_progress.correct_count + excluded.correct_count""",
            (card.type, card.base_word, card.target_form, score_after, now_text, increased_at, int(correct)),
        )
        connection.execute(
            """INSERT INTO practice_attempts
               (attempt_id, card_type, base_word, target_form, correct, score_before, score_after, answered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (attempt_id, card.type, card.base_word, card.target_form, int(correct), score_before, score_after, now_text),
        )
        return {"correct": correct, "score_before": score_before, "score_after": score_after}


def reset_card(path: Path, card: CardReference) -> int:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """UPDATE card_progress SET score = 0
               WHERE card_type = ? AND base_word = ? AND target_form = ?""",
            (card.type, card.base_word, card.target_form),
        )
    return 0


def card_exists(content_path: Path, card: CardReference) -> bool:
    if not content_path.exists():
        return False
    with sqlite3.connect(content_path) as connection:
        if card.type == "vocabulary":
            return connection.execute("SELECT 1 FROM vocabulary WHERE finnish = ?", (card.base_word,)).fetchone() is not None
        return connection.execute(
            """SELECT 1 FROM word_forms
               JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id
               WHERE vocabulary.finnish = ? AND word_forms.form = ?""",
            (card.base_word, card.target_form),
        ).fetchone() is not None


def get_stats(content_path: Path, progress_path: Path) -> dict[str, dict[str, int | float]]:
    with sqlite3.connect(content_path) as content:
        content.execute("ATTACH DATABASE ? AS progress", (str(progress_path),))
        vocabulary_total = content.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]
        form_total = content.execute("SELECT COUNT(*) FROM word_forms").fetchone()[0]
        # Progress rows for content removed by a later import must not affect current statistics.
        vocabulary_mastered = content.execute(
            """SELECT COUNT(*) FROM vocabulary
               JOIN progress.card_progress p ON p.card_type = 'vocabulary'
                  AND p.base_word = vocabulary.finnish AND p.target_form = '' AND p.score = 3"""
        ).fetchone()[0]
        form_mastered = content.execute(
            """SELECT COUNT(*) FROM word_forms
               JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id
               JOIN progress.card_progress p ON p.card_type = 'word_form'
                  AND p.base_word = vocabulary.finnish AND p.target_form = word_forms.form AND p.score = 3"""
        ).fetchone()[0]
    total = vocabulary_total + form_total
    mastered = vocabulary_mastered + form_mastered
    return {
        "vocabulary": {"total": vocabulary_total, "mastered": vocabulary_mastered},
        "word_forms": {"total": form_total, "mastered": form_mastered},
        "overall": {"total": total, "mastered": mastered, "mastery_percent": round((mastered / total * 100) if total else 0, 2)},
    }
