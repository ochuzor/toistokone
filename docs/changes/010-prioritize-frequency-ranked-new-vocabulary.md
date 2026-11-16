# Prioritize frequency-ranked new vocabulary in quiz batches

**Status:** Completed

## Problem

Never-practised score-0 vocabulary cards are selected randomly when they share
the same practice state, even though the content database contains frequency
ranks for them.

## Desired behavior

Within the existing score-0 selection step, prefer common never-practised
vocabulary cards while preserving the current selected vocabulary/word-form
mix and every existing quota rule.

## Scope

- Use exact case-folded base-word frequency ranks for vocabulary cards only.
- Preserve the score-0 candidate mix selected by existing recency/random rules.
- Replace its never-practised vocabulary choices with the highest-ranked
  eligible never-practised vocabulary cards.
- Place vocabulary absent from the frequency list after ranked words; retain
  randomized ordering for equal ranks.

## Acceptance criteria

- The selected vocabulary/form count, five-card maximum, and all non-score-0
  selection behavior are unchanged.
- Higher-ranked new vocabulary is preferred over lower-ranked or unranked
  vocabulary.
- Existing forms, previously practised score-0 cards, and quiz APIs are
  unchanged.
