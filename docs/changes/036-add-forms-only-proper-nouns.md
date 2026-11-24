# Support Forms-Only Dictionary Entries

## Problem

City names such as `Helsinki` need form practice but not a vocabulary meaning
quiz. The current base-card mastery requirement prevents their forms from
entering practice without an unnecessary meaning card.

## Desired behavior

Treat capitalized dictionary entries whose English meanings exactly match their
Finnish spelling as forms-only. Generate their forms immediately while keeping
translated proper nouns such as `Itävalta - Austria` as normal vocabulary.

## Scope

- Import `meaning_quizzable` with the forms-only heuristic.
- Exclude forms-only entries from vocabulary cards, distractors, totals, and
  focus-word requests.
- Immediately make their eligible form cards available.
- Support capitalized dictionary entries in Kaikki-index matching.

## Constraints

- Forms-only status affects form eligibility only, not contextual mastery
  signals, sentence selection, or progress statistics.
- No manual override syntax is introduced.

## Acceptance criteria

- `Helsinki - Helsinki` has forms but no vocabulary card.
- `sauna - sauna` and `Itävalta - Austria` retain vocabulary cards.
- Forms-only form cards are immediately eligible and progress imports remain
  untouched.

## Status

Implemented
