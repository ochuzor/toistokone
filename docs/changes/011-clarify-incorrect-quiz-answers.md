# Clarify incorrect quiz answers

**Status:** Completed

## Problem

When a learner selects an incorrect quiz option, its red highlight does not
make the incorrect choice visually distinct enough from the correct answer.

## Desired behavior

Strike through and color the selected incorrect answer. Keep the correct answer
highlighted, and fade the other unselected incorrect options.

## Scope

- Apply the styles only after an answer has been submitted.
- Keep correct-answer styling, scoring, and feedback behavior unchanged.

## Acceptance criteria

- A submitted wrong answer is struck through and red, without changing its font
  weight.
- The correct answer remains green.
- The other unselected incorrect options are faded.
- Unanswered options retain their current appearance.
