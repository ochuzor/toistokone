# Rank Contextual Reading-Break Sentences

## Problem

Reading breaks choose randomly from all sentences matching recent mastered
cards, so long or unfamiliar examples can appear as often as reinforcing ones.

## Desired behavior

Favor short sentences with more mastered tracked word families, while retaining
variety through weighted randomness. One or two known-but-unmastered families
are acceptable; three or more are strongly deprioritized.

## Scope

- Rank the existing recent-mastery sentence pool before selecting up to five
  distinct reading-break sentences.
- Treat untracked sentence tokens as neutral.
- Preserve the endpoint, timing, translation order, and no-exposure-history
  behavior.

## Constraints

- Do not change quiz selection, scoring, queue persistence, or content import.
- Retain existing mastered vocabulary and word-form surfaces as sentence anchors.

## Acceptance criteria

- Sentences with more mastered families rank above otherwise comparable ones.
- One or two known unmastered families remain eligible; three or more are much
  less likely, but not excluded.
- Returned sentences remain distinct and include ordered translations.

## Status

Implemented
