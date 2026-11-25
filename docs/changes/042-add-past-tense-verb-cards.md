# Add Past-Tense Verb Cards

## Problem

The generated verb profile covers only present indicative forms, omitting the
common past tense and its important stem changes.

## Desired behavior

Generate affirmative active indicative-past cards for all six grammatical
persons, alongside the existing present-tense cards.

## Scope

- Add `past-1sg` through `past-3pl` Kaikki slots with the existing person prompts.
- Rebuild the Kaikki index and preserve the current form-card quiz flow.

## Constraints

- Exclude negative, passive, multi-word, non-finite, rare, and possessive forms.
- Preserve mastery gating, queue selection, cooldown, and progress data.

## Acceptance criteria

- `tehdä → teki` generates `verb:past-3sg` with prompt `hän ____`.
- All six affirmative past persons generate where Kaikki supplies them.
- Negative and passive past forms do not generate cards.

## Status

Implemented
