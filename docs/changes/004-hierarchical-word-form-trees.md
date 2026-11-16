# Add hierarchical word-form trees

**Status:** Completed

## Problem

`word-forms.txt` supports only forms directly under dictionary words. It cannot
represent derivation chains such as `auto → autossa → autossani`.

## Desired behavior

Allow any declared form to declare its own children. Direct children of a
dictionary word unlock after vocabulary mastery; nested children unlock after
their immediate parent form is mastered. Each form has exactly one parent.

## Scope

- Store immediate parent links in the disposable content database.
- Parse declarations in any order and validate roots, duplicate children,
  ambiguous parents, and cycles.
- Preserve progress keys as root dictionary word plus target form.
- Use a target's immediate parent and siblings as its word-form answer pool.
- Retain base-form cards and current direct-child syntax.

## Constraints

- Content imports rebuild only `content.sqlite`; they never modify
  `progress.sqlite`.
- A missing-sentence form remains ineligible, which also blocks its children.
- Existing batch quotas, cooldown, and mastery-aware sentence weighting remain
  unchanged.

## Acceptance criteria

- Direct and nested form declarations import into a validated rooted tree.
- Direct children require mastered vocabulary; nested children require a
  mastered immediate parent form.
- Resetting a parent makes its descendants ineligible without erasing scores.
- Distractors are limited to the parent and direct siblings.
- Pipeline, quiz, build, and Playwright verification pass.
