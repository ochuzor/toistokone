# Add Nominative Plural Grammar Cards

## Problem

The generated nominal profile contains only singular cases, omitting the
common nominative plural (*t-monikko*) form.

## Desired behavior

Generate a nominative-plural card such as `talo → talot` after its base
vocabulary card is mastered.

## Scope

- Add the Kaikki `nominative` + `plural` nominal slot.
- Label its prompt `Nominatiivi, monikko (mitkä?)`.
- Rebuild stale Kaikki subset indexes when the profile changes.

## Constraints

- Do not add other plural cases or change the existing quiz flow.
- Preserve base-word mastery unlocking and multiple-choice eligibility rules.

## Acceptance criteria

- Kaikki nominative-plural forms become generated word-form cards.
- They are unavailable before base vocabulary mastery and use existing options.

## Status

Implemented
