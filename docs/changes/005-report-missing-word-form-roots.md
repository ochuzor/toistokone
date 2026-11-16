# Report missing word-form roots and reject cycles

**Status:** Completed

## Problem

The import report has only line-by-line diagnostics for invalid form trees. It
does not provide a concise list of unresolved root parents, and a form cycle
can be skipped while the rest of the content database is replaced.

## Desired behavior

List unresolved word-form roots alphabetically in the import report, grouping
their skipped descendants beneath each root.
Reject any form cycle as a fatal validation error, write the report, and leave
the existing content and progress databases untouched.

## Scope

- Report parents that are neither dictionary entries nor declared forms.
- Exclude valid nested parents and cycle members from that list.
- Detect and display complete cycle paths.
- Treat cycles as fatal for both normal and dry-run imports.

## Acceptance criteria

- Normal and dry-run reports list missing roots in alphabetical order, with
  their skipped descendants grouped beneath them.
- A cycle produces a clear error path and a non-zero CLI exit.
- Fatal cycles do not replace `content.sqlite` or modify `progress.sqlite`.
- Existing non-fatal diagnostics remain available.
- Relevant pipeline tests pass.
