# Add Contextual Reading Breaks

## Problem

Most imported Finnish-English sentences are not exposed during normal quiz
practice.

## Desired behavior

After a random 3–10 completed quizzes, show one reading-break page containing
up to five Finnish sentences and their translations. It should draw randomly
from sentences containing the 30 most recently practised mastered vocabulary
or word-form surfaces, while allowing other unmastered words in the sentence.

## Scope

- Add a read-only API for contextual sentence breaks.
- Persist the scheduled or active break with the frontend practice queue.
- Render the reading-break page and return to the quiz queue with **Next**.
- Update user-facing and technical documentation.

## Constraints

- Do not change quiz selection, scoring, practice history, or the import pipeline.
- Do not record sentence exposure history; repeated sentences are allowed.
- Show fewer than five sentences when the matching pool is smaller; skip an
  empty or unavailable break and reschedule it.

## Acceptance criteria

- Mastered vocabulary and form cards both contribute surfaces to sentence matching.
- A break contains distinct sentences with their stored translation order.
- A refresh preserves an active reading break.
- Clicking its **Next** continues normal practice without updating any score.

## Status

Implemented
