# Ensure Unique Vocabulary Answer Options

## Problem

Different Finnish dictionary entries can share an identical displayed English
meaning group. The quiz could render that text as both the correct answer and a
distractor, making one visually identical choice incorrect.

## Desired behavior

Vocabulary questions never include a distractor whose displayed meaning group
is identical to the correct option.

## Scope

- Filter vocabulary distractors by their rendered meaning-group text.
- Add a regression test for `vai` and `tai`, both translated as `or`.

## Acceptance criteria

- Every displayed vocabulary option is unique.
- Selecting the only displayed correct text cannot be marked incorrect because
  another entry has the same translation.

## Status

Implemented
