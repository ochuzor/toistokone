# Remove Redundant Singular-Nominative Form Cards

## Problem

Every singular-nominative form card repeats the dictionary headword already
practised by the vocabulary meaning card, adding an unnecessary score and
practice step.

## Desired behavior

Do not generate or quiz singular-nominative form cards. Keep nominative plural
cards, including ordinary nouns such as `talo → talot` and plural pronouns such
as `ne → ne`.

## Scope

- Remove the singular nominative slot from the normal nominal profile.
- Rebuild the reusable Kaikki index after the profile change.
- Update documentation and regression tests.

## Constraints

- Continue using nominative tags to identify singular and plural pronoun
  paradigms.
- Preserve nominative-plural cards and all other supported nominal forms.
- Never delete or reset existing progress records during an import.

## Acceptance criteria

- A normal nominal entry has no `nominal:nominative` card.
- Its `nominal:nominative-plural` card remains available where applicable.
- Singular and plural pronoun forms remain assigned to the correct profiles.
- Existing singular-nominative progress rows remain untouched and are not
  eligible for practice after rebuilding content.

## Status

Implemented
