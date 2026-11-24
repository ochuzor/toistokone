# Add Outer Local-Case Grammar Cards

## Problem

Useful forms such as `aamulla` are not generated or tracked because the
nominal profiles omit the outer local cases.

## Desired behavior

Generate adessive, ablative, and allative cards wherever the current singular
nominal profile applies, including corresponding plural-pronoun entries.

## Scope

- Add `Adessiivi (millä?)`, `Ablatiivi (miltä?)`, and `Allatiivi (mille?)`.
- Rebuild the Kaikki form index and let existing contextual features track the
  new generated surfaces after import.

## Constraints

- Do not add ordinary plural outer-local cards or other new case families.
- Preserve existing POS gates, progress, and quiz selection rules.

## Acceptance criteria

- `aamu → aamulla` and representative ablative/allative forms generate cards.
- Singular and plural pronoun profiles receive only their respective forms.
- The new surfaces are tracked by content health after reimport.

## Status

Implemented
