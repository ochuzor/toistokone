# Add early nominal grammar guides

## Problem

The Allatiivi-only guide appears only after later nominal stages, so learners
may not encounter the teaching feature for some time.

## Desired behavior

Offer the same first-encounter guide, later help, and detail page for the early
Genetiivi, Partitiivi, and Inessiivi form cards, while retaining Allatiivi.

## Scope

- Permit the three target form keys in grammar-guide validation.
- Add English-led Markdown guides with Finnish examples for all three forms.
- Update tests and product documentation.

## Constraints

Reuse the existing guide API and durable acknowledgement state. Do not alter
card selection, scoring, unlock stages, or mastery.

## Acceptance criteria

- The four supported nominal guide files import successfully.
- Their matching quiz cards carry guide metadata.
- Unsupported guide target forms still fail preflight validation.

## Status

Implemented.
