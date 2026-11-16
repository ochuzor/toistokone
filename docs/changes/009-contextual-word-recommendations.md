# Add contextual frequency-based word recommendations

**Status:** Completed

## Problem

The application has no way to suggest useful next vocabulary from the learner's
curated word list and the available sentence corpus.

## Desired behavior

Show a reviewable list of common, unknown surface forms that occur beside
existing dictionary words or declared forms. The learner decides whether to
add a suggestion manually to `dictionary.txt`.

## Scope

- Require `frequency/fi_50k.txt` on every content import and store its ranks
  and counts in the content database.
- Reject missing, malformed, non-positive, or duplicate frequency entries
  without replacing the current content database.
- Recommend only exact, three-or-more-character frequency tokens that co-occur
  with a tracked word family; exclude known base words and forms.
- Rank primarily by frequency, then contextual family breadth and occurrences.
- Provide a dedicated browser page with supporting Finnish-English examples.

## Acceptance criteria

- The normal pipeline stores valid frequency data and leaves progress intact.
- Invalid required frequency input fails safely and clearly.
- Recommendations are contextual, frequency-first, and exclude known/short
  tokens.
- The API and review page show ranks and sentence examples.
- The feature does not add vocabulary automatically or change quiz selection.
