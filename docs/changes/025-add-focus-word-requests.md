# Add One-Time Focus Word Requests

## Problem

New class vocabulary competes with every other score-0 word, so learners cannot
request that a timely word enters the next available new-vocabulary slot.

## Desired behavior

Let learners select a current, never-practised dictionary word to enter the
next generated batch with an available score-0 vocabulary slot.

## Scope

- Add persistent one-time focus requests and a searchable Focus words page.
- Prioritize requested words oldest-first within selected score-0 vocabulary
  positions.
- Clear a request once its card enters a generated batch.

## Constraints

- Preserve queue persistence, quotas, vocabulary/form mix, review selection,
  ranking, diversity, and learning chains for other cards.
- Allow only current score-0, never-practised vocabulary words.

## Acceptance criteria

- Learners can add and remove a focus request from the browser.
- Requested words enter the next eligible batch and clear afterward.
- Existing queue cards are never rewritten.

## Status

Implemented
