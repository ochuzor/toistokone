from __future__ import annotations

import re


TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def tokens(text: str) -> set[str]:
    """Return Unicode word tokens in the same case-insensitive form used for lookup."""
    return set(TOKEN_PATTERN.findall(text.casefold()))


def whole_word_pattern(form: str) -> re.Pattern[str]:
    """Match a Unicode word only when it is not embedded in a longer word."""
    return re.compile(rf"(?<!\w){re.escape(form)}(?!\w)", re.IGNORECASE)


def matches_form(sentence: str, form: str) -> bool:
    return whole_word_pattern(form).search(sentence) is not None


def blank_form(sentence: str, form: str) -> str:
    return whole_word_pattern(form).sub("____", sentence)
