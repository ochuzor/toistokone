# Report forms with insufficient practice sentences

**Status:** Completed

## Problem

The import report does not show which valid form cards have too little sentence
content for varied contextual practice.

## Desired behavior

Report every valid imported base form and descendant with fewer than two
distinct supporting Finnish sentences, grouped under its root dictionary word.
Use the same exact case-insensitive whole-word matching as quiz generation.

## Scope

- Count distinct Finnish sentences, not translations or repeated occurrences.
- Include all valid imported form cards, regardless of mastery state.
- Exclude unresolved or cyclic form-tree entries.
- Keep this informational; existing quiz eligibility does not change.

## Acceptance criteria

- Reports group under-supported forms alphabetically by root word and form.
- Counts correctly distinguish zero, one, and two supporting sentences.
- Repeated occurrences, multiple translations, case differences, and substrings
  do not inflate the count.
- Normal and dry-run reports include the audit without modifying progress data.
