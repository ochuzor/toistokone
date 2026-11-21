# Generate grammar form cards from Kaikki

**Status:** Completed

## Problem

Manually maintaining `word-forms.txt` is slow and error-prone, while sentence
availability should not determine whether basic grammar forms are practised.

## Desired behavior

Generate labelled nominal and verb form cards from the local Kaikki Finnish
lexicon for every applicable dictionary word. Quiz them with grammar prompts.

## Scope

- Replace `word-forms.txt` with an ignored reusable Kaikki morphology index.
- Generate six singular nominal cases and six present-indicative active verb
  forms, selecting the first non-rare single-word candidate per slot.
- Report unsupported words and alternative candidates.
- Keep vocabulary quizzes and progress data intact.

## Acceptance criteria

- A later content import reuses the Kaikki index unless its source changes.
- `talo — Inessiivi (missä?)` and `tehdä — hän ____` form questions use
  same-profile distractors and require no sentence.
- Words without a usable profile remain available as vocabulary cards.
- Content rebuilds do not delete or reset progress data.
