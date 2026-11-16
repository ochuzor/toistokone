# Add mastery-aware sentence selection

**Status:** Completed

## Problem

Word-form quiz sentences are selected uniformly from every sentence matching
the target form. As the content corpus grows, including Tatoeba imports, the
app does not prefer sentences whose surrounding tracked vocabulary the learner
already knows.

## Desired behavior

Favor sentence context made up of mastered vocabulary families while retaining
some variety. A vocabulary family is known when its vocabulary card is score
3; all of that family's imported forms are known. Count each distinct,
non-target tracked family once. Untracked words do not affect difficulty.

## Scope

- Add a content-only `sentence_tokens` index for scalable token lookups.
- Select matching word-form sentences with weights of 16, 8, 4, and 1 for 0,
  1, 2, and 3+ unmastered tracked families respectively.
- Keep exact whole-word matching as the final check before blanking.
- Preserve the separate content/progress database ownership model.

## Constraints

- The index is rebuilt only with `content.sqlite`; imports never modify
  `progress.sqlite`.
- Use Unicode-aware case-folded tokens.
- When a form belongs to multiple families, treat it as known if any family is
  mastered, consistent with the existing homograph limitation.

## Acceptance criteria

- Imports create and populate a token index for every sentence.
- Word-form sentence selection favors contexts with 0–2 unmastered tracked
  families according to the agreed weights.
- Repeated forms count once per family, and the target family is excluded.
- Existing matching, translations, scoring, queue behavior, and content-import
  safety remain intact.
- Pipeline/quiz tests, frontend build, and Playwright verification pass.
