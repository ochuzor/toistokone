# Filter Tatoeba sentences using frequency and length

**Status:** Completed

## Problem

The raw Tatoeba export contains many sentences that are too long or contain
too many uncommon Finnish words for beginner practice. It cannot be imported
unchanged without reducing the pedagogical quality of the sentence pool.

## Desired behavior

Provide a one-time standalone extractor that uses the local 50,000-word
frequency list to create an import-ready Tatoeba sentence file. Keep only
sentences with at most eight Finnish word tokens and no more than two tokens
outside the 10,000 most frequent forms; forms absent from the list are also
uncommon.

## Scope

- Read `tatoeba/fi_50k.txt` and `tatoeba/finn-eng.txt`.
- Write `sentences/tatoeba-filtered.txt` in the existing sentence-source
  format, consolidating duplicate Finnish sentences and translations.
- Write an audit report with retained, rejected, malformed, and duplicate
  totals.
- Refuse accidental output overwrites unless explicitly forced.
- Keep the normal content import pipeline independent of the raw export.

## Acceptance criteria

- The extractor applies the approved length and frequency thresholds.
- Unknown frequency forms count toward the uncommon-token limit.
- The generated source is accepted by the normal content importer.
- The report records filtering and deduplication totals.
- Existing content and progress databases are not modified.
