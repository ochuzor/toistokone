from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
CREATE INDEX IF NOT EXISTS idx_attempts_answered_at ON practice_attempts(answered_at);
CREATE TABLE IF NOT EXISTS focus_vocabulary (
  base_word TEXT PRIMARY KEY,
  requested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_focus_vocabulary_requested ON focus_vocabulary(requested_at);
"""


def initialize_progress_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(PROGRESS_SCHEMA)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(card_progress)")}
        if "last_score_increased_at" not in columns:
            connection.execute("ALTER TABLE card_progress ADD COLUMN last_score_increased_at TEXT")


def get_content_revision(path: Path) -> str:
    """Return the pipeline revision, with a stable fallback for legacy content."""
    fallback = f"legacy-{path.stat().st_mtime_ns}-{path.stat().st_size}"
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                "SELECT value FROM content_metadata WHERE key = 'revision'"
            ).fetchone()
    except sqlite3.OperationalError:
        return fallback
    return row[0] if row else fallback


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


def list_vocabulary(content_path: Path, progress_path: Path, query: str = "", limit: int = 50) -> list[dict[str, object]]:
    """Return current dictionary entries with progress and focus-request state."""
    normalized_query = query.casefold().strip()
    with sqlite3.connect(content_path) as connection:
        connection.execute("ATTACH DATABASE ? AS progress", (str(progress_path),))
        rows = connection.execute(
            """SELECT vocabulary.finnish, vocabulary_meanings.meaning,
                      COALESCE(card_progress.score, 0), card_progress.last_practiced_at,
                      focus_vocabulary.requested_at
               FROM vocabulary
               JOIN vocabulary_meanings ON vocabulary_meanings.vocabulary_id = vocabulary.id
               LEFT JOIN progress.card_progress ON card_progress.card_type = 'vocabulary'
                  AND card_progress.base_word = vocabulary.finnish AND card_progress.target_form = ''
               LEFT JOIN progress.focus_vocabulary ON focus_vocabulary.base_word = vocabulary.finnish
               ORDER BY vocabulary.finnish, vocabulary_meanings.ordinal"""
        ).fetchall()
    entries: dict[str, dict[str, object]] = {}
    for finnish, meaning, score, last_practiced_at, requested_at in rows:
        entry = entries.setdefault(finnish, {
            "finnish": finnish,
            "meanings": [],
            "score": score,
            "last_practiced_at": last_practiced_at,
            "focus_requested_at": requested_at,
        })
        entry["meanings"].append(meaning)  # type: ignore[union-attr]
    matches = [
        entry for entry in entries.values()
        if not normalized_query
        or normalized_query in str(entry["finnish"]).casefold()
        or any(normalized_query in meaning.casefold() for meaning in entry["meanings"])
    ]
    return matches[:limit]


def list_focus_words(content_path: Path, progress_path: Path) -> list[dict[str, object]]:
    """Return every outstanding focus request, oldest first."""
    with sqlite3.connect(content_path) as connection:
        connection.execute("ATTACH DATABASE ? AS progress", (str(progress_path),))
        rows = connection.execute(
            """SELECT vocabulary.finnish, vocabulary_meanings.meaning,
                      COALESCE(card_progress.score, 0), card_progress.last_practiced_at,
                      focus_vocabulary.requested_at
               FROM progress.focus_vocabulary
               JOIN vocabulary ON vocabulary.finnish = focus_vocabulary.base_word
               JOIN vocabulary_meanings ON vocabulary_meanings.vocabulary_id = vocabulary.id
               LEFT JOIN progress.card_progress ON card_progress.card_type = 'vocabulary'
                  AND card_progress.base_word = vocabulary.finnish AND card_progress.target_form = ''
               ORDER BY focus_vocabulary.requested_at, vocabulary.finnish, vocabulary_meanings.ordinal"""
        ).fetchall()
    entries: dict[str, dict[str, object]] = {}
    for finnish, meaning, score, last_practiced_at, requested_at in rows:
        entry = entries.setdefault(finnish, {
            "finnish": finnish,
            "meanings": [],
            "score": score,
            "last_practiced_at": last_practiced_at,
            "focus_requested_at": requested_at,
        })
        entry["meanings"].append(meaning)  # type: ignore[union-attr]
    return list(entries.values())


def request_focus_word(
    content_path: Path,
    progress_path: Path,
    base_word: str,
    now: datetime | None = None,
) -> dict[str, str]:
    """Persist a one-time request for a current, never-practised vocabulary card."""
    with sqlite3.connect(content_path) as content:
        exists = content.execute("SELECT 1 FROM vocabulary WHERE finnish = ?", (base_word,)).fetchone()
    if not exists:
        raise LookupError("Vocabulary word does not exist in current content")
    with sqlite3.connect(progress_path) as connection:
        row = connection.execute(
            """SELECT score, last_practiced_at FROM card_progress
               WHERE card_type = 'vocabulary' AND base_word = ? AND target_form = ''""",
            (base_word,),
        ).fetchone()
        if row and (row[0] != 0 or row[1] is not None):
            raise ValueError("Only new, never-practised vocabulary words can be focused")
        existing = connection.execute(
            "SELECT requested_at FROM focus_vocabulary WHERE base_word = ?", (base_word,)
        ).fetchone()
        if existing:
            return {"base_word": base_word, "requested_at": existing[0]}
        requested_at = (now or _now()).isoformat()
        connection.execute(
            "INSERT INTO focus_vocabulary (base_word, requested_at) VALUES (?, ?)", (base_word, requested_at)
        )
    return {"base_word": base_word, "requested_at": requested_at}


def remove_focus_word(progress_path: Path, base_word: str) -> dict[str, str] | None:
    with sqlite3.connect(progress_path) as connection:
        row = connection.execute(
            "SELECT requested_at FROM focus_vocabulary WHERE base_word = ?", (base_word,)
        ).fetchone()
        if not row:
            return None
        connection.execute("DELETE FROM focus_vocabulary WHERE base_word = ?", (base_word,))
    return {"base_word": base_word, "requested_at": row[0]}


def consume_focus_words(progress_path: Path, base_words: list[str]) -> None:
    if not base_words:
        return
    with sqlite3.connect(progress_path) as connection:
        connection.executemany("DELETE FROM focus_vocabulary WHERE base_word = ?", ((word,) for word in base_words))


def card_exists(content_path: Path, card: CardReference) -> bool:
    if not content_path.exists():
        return False
    with sqlite3.connect(content_path) as connection:
        if card.type == "vocabulary":
            return connection.execute("SELECT 1 FROM vocabulary WHERE finnish = ?", (card.base_word,)).fetchone() is not None
        return connection.execute(
            """SELECT 1 FROM word_forms
               JOIN vocabulary ON vocabulary.id = word_forms.vocabulary_id
               WHERE vocabulary.finnish = ? AND word_forms.card_key = ?""",
            (card.base_word, card.target_form),
        ).fetchone() is not None


def _local_activity(
    progress_path: Path,
    timezone_name: str,
    now: datetime | None = None,
) -> dict[str, object]:
    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("timezone must be a valid IANA timezone name") from error

    now = now or _now()
    today = now.astimezone(local_timezone).date()
    first_day = today - timedelta(days=13)
    start = datetime.combine(first_day, time.min, tzinfo=local_timezone).astimezone(timezone.utc)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=local_timezone).astimezone(timezone.utc)
    daily: dict[date, dict[str, object]] = {
        first_day + timedelta(days=offset): {
            "attempts": 0,
            "correct": 0,
            "cards": set(),
            "score_increases": 0,
            "newly_mastered": 0,
        }
        for offset in range(14)
    }
    with sqlite3.connect(progress_path) as connection:
        rows = connection.execute(
            """SELECT card_type, base_word, target_form, correct, score_before, score_after, answered_at
               FROM practice_attempts WHERE answered_at >= ? AND answered_at < ?""",
            (start.isoformat(), end.isoformat()),
        )
        for card_type, base_word, target_form, correct, score_before, score_after, answered_at in rows:
            local_day = datetime.fromisoformat(answered_at).astimezone(local_timezone).date()
            record = daily[local_day]
            record["attempts"] = int(record["attempts"]) + 1
            record["correct"] = int(record["correct"]) + correct
            record["cards"].add((card_type, base_word, target_form))  # type: ignore[union-attr]
            record["score_increases"] = int(record["score_increases"]) + int(score_after > score_before)
            record["newly_mastered"] = int(record["newly_mastered"]) + int(score_before < 3 and score_after == 3)

        active_days = {
            datetime.fromisoformat(answered_at).astimezone(local_timezone).date()
            for (answered_at,) in connection.execute(
                "SELECT answered_at FROM practice_attempts WHERE answered_at < ?", (end.isoformat(),)
            )
        }

    days = []
    for day, record in daily.items():
        attempts = int(record["attempts"])
        correct = int(record["correct"])
        days.append({
            "date": day.isoformat(),
            "attempts": attempts,
            "correct": correct,
            "accuracy_percent": round((correct / attempts * 100) if attempts else 0, 2),
            "unique_cards": len(record["cards"]),
            "score_increases": int(record["score_increases"]),
            "newly_mastered": int(record["newly_mastered"]),
        })

    streak_day = today if today in active_days else today - timedelta(days=1)
    streak_days = 0
    while streak_day in active_days:
        streak_days += 1
        streak_day -= timedelta(days=1)
    return {"today": days[-1], "days": days, "streak_days": streak_days}


def get_stats(
    content_path: Path,
    progress_path: Path,
    timezone_name: str = "UTC",
    now: datetime | None = None,
) -> dict[str, object]:
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
                  AND p.base_word = vocabulary.finnish AND p.target_form = word_forms.card_key AND p.score = 3"""
        ).fetchone()[0]
    total = vocabulary_total + form_total
    mastered = vocabulary_mastered + form_mastered
    return {
        "vocabulary": {"total": vocabulary_total, "mastered": vocabulary_mastered},
        "word_forms": {"total": form_total, "mastered": form_mastered},
        "overall": {"total": total, "mastered": mastered, "mastery_percent": round((mastered / total * 100) if total else 0, 2)},
        "activity": _local_activity(progress_path, timezone_name, now),
    }
