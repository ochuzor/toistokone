# Batch content database imports

**Status:** Completed

## Problem

The expanded sentence corpus makes normal content imports noticeably slow.
Profiling shows that repeated SQLite calls for each sentence, translation, and
token are the dominant cost; parsing and validation remain fast.

## Desired behavior

Build the content database faster without changing input formats, imported
data, reports, quiz behavior, schema, or progress-data protection.

## Scope

- Batch sentence inserts, then retrieve sentence IDs once.
- Batch translation and token-index inserts using those IDs.
- Preserve sentence order, translation ordinals, unique token behavior,
  integrity checks, and atomic database replacement.
- Keep dry-run behavior unchanged.

## Acceptance criteria

- Imported sentences, translations, and token mappings match the prior
  per-sentence behavior.
- Progress data is not modified during normal or dry-run imports.
- Relevant pipeline tests pass.
- The normal build is materially faster on the current corpus.
