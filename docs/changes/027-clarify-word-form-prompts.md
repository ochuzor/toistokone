# Clarify Standard Word-Form Quiz Prompts

## Problem

Standard word-form prompts combine a base form and response frame in one
equally prominent line, making the target task less clear.

## Desired behavior

Show nominal base words as the primary prompt with a compact instruction that
names the requested case. Keep verbs as a muted “Base form” hint above their
response frame. Leave vocabulary and sentence-context cards unchanged.

## Scope

- Add an optional quiz-question hint.
- Render nominal and verb word-form prompts differently in Practice.
- Add responsive styling for the layered prompt.

## Constraints

- Existing saved queues without a hint must remain valid.
- Do not change quiz selection, scoring, or content data.

## Acceptance criteria

- `olla` appears as a Base form hint above a prominent `hän ____` prompt.
- Nominal cards show the base word prominently, followed by “Choose the” plus
  the form name and a subdued Finnish question cue.
- Sentence-context and vocabulary prompts remain single primary prompts.

## Status

Implemented
