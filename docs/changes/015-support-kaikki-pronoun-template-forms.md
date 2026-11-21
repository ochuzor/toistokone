# Support Kaikki pronoun-template forms

## Problem

Kaikki stores the singular inflection table for `se` on a related `ne` entry
using the `fi-decl-pron/se` template. The importer only reads forms from an
exact headword with the `declension` source, so it incorrectly reports `se` as
having no usable profile.

## Desired behavior

Generate the existing supported nominal cards for a dictionary lemma when a
Kaikki pronoun inflection template identifies that lemma as its owner. Accept
safe nominal forms from Kaikki's `inflection` source as well as `declension`.

## Scope

- Recognize `fi-decl-pron/<lemma>` template ownership while building the
  reusable Kaikki subset index.
- Version the index signature so pre-existing indexes rebuild.
- Add regression coverage and regenerate the content import report.

## Constraints

- Keep the current supported nominal slots and all form safety filters.
- Do not modify progress data or quiz behavior.

## Acceptance criteria

- `se` produces its supported singular nominal cards, including `sitä` and
  `siinä`, and is absent from the missing-profile report.
- An old Kaikki index is rebuilt after this parser change.
- Backend tests and the content import complete successfully.

## Status

Implemented
