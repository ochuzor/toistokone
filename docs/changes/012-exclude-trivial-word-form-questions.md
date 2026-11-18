# Exclude trivial word-form questions

**Status:** Completed

## Problem

A word-form card can be generated with only its correct answer, which does not
test recall but can still increase mastery.

## Desired behavior

Only generate word-form questions with at least two distinct options: the
target form and an immediate-branch distractor.

## Scope

- Exclude word-form cards whose parent-and-sibling branch has no distinct
  distractor.
- Use the same branch-option calculation for eligibility and question output.
- Preserve sentence selection, unlocking, scoring, and existing two-to-four
  option questions.

## Acceptance criteria

- A mastered form family with only a base form is not added to a quiz batch.
- Eligible word-form questions always have at least two distinct options.
- Word-form questions with a parent or sibling remain eligible.
