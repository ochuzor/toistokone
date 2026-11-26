# Show Learning-Set Words and Progress

## Problem

The Learning sets page shows only aggregate progress, so a learner cannot see
which words belong to a set or their individual current mastery.

## Desired behavior

Selecting a learning set opens a detail page listing its words in set order,
with translations, base-card mastery icons, and mastered-form summaries.

## Scope

- Add a learning-set detail API and route.
- Show compact per-word vocabulary and form progress without listing every form.

## Acceptance criteria

- A set detail page shows every member word and its translations.
- Each word shows its current base-card mastery icon and form mastery count.
- Forms-only entries display as base-mastered, consistent with existing set totals.
- Unknown set IDs return a not-found response.

## Status

Implemented
