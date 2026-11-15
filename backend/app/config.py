from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigurationError(ValueError):
    """Raised when local configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    quiz_batch_size: int


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Load local settings, with environment variables overriding `.env`."""
    dotenv_values = _read_dotenv(PROJECT_ROOT / ".env")
    environment = os.environ if env is None else env
    raw_batch_size = environment.get("QUIZ_BATCH_SIZE", dotenv_values.get("QUIZ_BATCH_SIZE", "20"))

    try:
        quiz_batch_size = int(raw_batch_size)
    except (TypeError, ValueError) as error:
        raise ConfigurationError("QUIZ_BATCH_SIZE must be a positive integer") from error
    if quiz_batch_size <= 0:
        raise ConfigurationError("QUIZ_BATCH_SIZE must be a positive integer")
    return Settings(quiz_batch_size=quiz_batch_size)
