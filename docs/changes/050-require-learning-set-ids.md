# Require Learning-Set IDs

## Problem

Learning sets currently use their filename stems as identity. Renaming a file
therefore breaks active-set state and would break future learning-path references.

## Desired behavior

Every learning-set file declares an immutable lower-case kebab-case ID. Missing,
invalid, or duplicate IDs fail pipeline preflight validation.

## Scope

- Require a small Markdown front-matter block containing `id:` before the title.
- Use the declared ID as the content-database learning-set key.
- Report malformed, missing, and conflicting IDs with source locations.

## Constraints

- Do not alter user-authored learning-set files automatically.
- Preserve existing title, word, and coverage behavior.

## Acceptance criteria

- Renaming a file while retaining its ID preserves its identity.
- Missing, malformed, and duplicate IDs fail before expensive import work.

## Status

Implemented
