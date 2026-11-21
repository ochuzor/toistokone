# Reinforce mastered forms with contextual sentences

**Status:** Completed

## Problem

Grammar prompts establish individual forms but do not expose mastered forms in
natural Finnish.

## Desired behavior

Within the existing score-3 batch allocation, use a matching blanked sentence
and translation for a selected word-form card when possible. Otherwise keep
the grammar prompt.

## Scope

- Do not change batch composition, scoring, or create a separate practice mode.
- Apply contextual prompts only to score-3 word-form cards.
- Favor sentences with other mastered tracked families.

## Acceptance criteria

- A score-3 form with sentence coverage is blanked in context with translations.
- Score-0–2 forms and uncovered score-3 forms use grammar prompts.
- Score-3 remains permanent unless manually reset.
