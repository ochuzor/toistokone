from __future__ import annotations

import re


def whole_word_pattern(form: str) -> re.Pattern[str]:
    """Match a Unicode word only when it is not embedded in a longer word."""
    return re.compile(rf"(?<!\w){re.escape(form)}(?!\w)", re.IGNORECASE)


def matches_form(sentence: str, form: str) -> bool:
    return whole_word_pattern(form).search(sentence) is not None


def blank_form(sentence: str, form: str) -> str:
    return whole_word_pattern(form).sub("____", sentence)
