# Stage Verb-Form Introduction

## Problem

All present and past cards for a mastered verb become eligible together, adding
up to twelve new forms at once.

## Desired behavior

Introduce verb cards in four stages: present singular, past singular, present
plural, then past plural. Mastering two cards in a stage unlocks the next.

## Scope

- Apply staged unlocks only to the `verb` profile.
- Keep previously practised later-stage cards available.
- Restrict verb question choices to currently unlocked cards.
- Refresh saved browser practice queues.

## Constraints

- Preserve nominal-form and forms-only-entry behavior.
- Derive state from current card keys and progress; do not add a database table.

## Acceptance criteria

- A mastered verb first offers only its three present-singular forms.
- Two mastered forms advance each subsequent stage.
- Locked forms cannot be selected or used as answer choices.
- Existing practised cards remain eligible and saved queues refresh.

## Status

Implemented
