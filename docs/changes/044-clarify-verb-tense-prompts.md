# Clarify Verb-Tense Prompts

## Problem

Person-only prompts such as `hän ____` are valid for both present and past
verb forms, making direct form questions ambiguous.

## Desired behavior

Direct verb-form questions show a subdued present-tense (`preesens`) or
past-tense (`imperfekti`) cue beneath the person prompt.

## Scope

- Derive the cue from the existing `verb:present-*` and `verb:past-*` card keys.
- Do not alter generated content, quiz selection, answer options, or sentence
  reinforcement prompts.

## Constraints

- Keep the cue limited to direct form-choice prompts that show a base-form hint.

## Acceptance criteria

- Present and past cards with the same person prompt are distinguishable.
- Sentence-context cards and nominal-form cards retain their existing layouts.

## Status

Implemented
