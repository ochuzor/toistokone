# Add Markdown Learning Sets

## Problem

Vocabulary, forms, and sentence reinforcement lack a learner-defined layer that
connects material from a class, textbook unit, or practical topic.

## Desired behavior

Import named Markdown learning sets, allow one active set, and use it to prefer
eligible new cards and contextual reading-break sentences without changing
review or mastery rules.

## Scope

- Read direct-child `learning-sets/*.md` files with one H1 title and a list of
  at least ten dictionary headwords.
- Reject invalid or unknown entries during import and report coverage warnings.
- Store set membership in content and active selection in progress.
- Add API, navigation page, active-set practice indication, and selection
  preferences for set vocabulary/forms and sentence breaks.

## Constraints

- Keep focus-word requests ahead of learning-set preferences.
- Preserve review quotas, cooldowns, form staging, and content/progress
  database separation.
- Do not add in-app authoring or generated sets.

## Acceptance criteria

- Valid sets import with progress totals; invalid word references fail import.
- One set can be activated or cleared in the browser.
- Eligible score-0 set cards and set-related reading-break sentences are
  preferred with normal fallbacks.

## Status

Implemented
