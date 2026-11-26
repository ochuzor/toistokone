# Add an Allatiivi grammar guide

## Problem

Form cards introduce Finnish grammar without a concise explanation at the point
of first use.

## Desired behavior

The first `nominal:allative` card shows a short Allatiivi guide before its
unchanged question. Later cards offer compact help and a full guide page. The
acknowledgement survives browser changes but never changes card progress.

## Scope

- Import and validate Markdown grammar guides from `grammar-guides/`.
- Store guide content in content SQLite and acknowledgement in progress SQLite.
- Enrich matching quiz questions, add guide APIs, Practice interstitial/help,
  and a detail route.
- Ship the English-language Allatiivi pilot guide.

## Constraints

Only `nominal:allative` is supported in this slice. Queue selection, scoring,
unlocking, and mastery remain unchanged.

## Acceptance criteria

- Invalid guide metadata stops the pipeline before expensive imports.
- First encounter requires acknowledgement before displaying the same quiz card.
- Later cards have help and a full guide link.
- Seen state is durable in `progress.sqlite` and does not create card progress.

## Status

Implemented.
