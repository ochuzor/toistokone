# Optimize the Practice Screen for Mobile

## Problem

The practice screen works on narrow displays but its desktop-oriented spacing
and inline feedback actions make repeated phone practice less comfortable.

## Desired behavior

Make the practice flow touch-friendly on phones and provide a compact floating
Next arrow after an answer is saved.

## Scope

- Refine mobile padding, header spacing, options, and feedback on `/practice`.
- Make Next a safe-area-aware circular floating arrow at the mobile bottom-right
  after feedback.
- Keep Reset mastery secondary and in document flow.

## Constraints

- Preserve desktop layout, quiz behavior, progress persistence, and APIs.
- Do not change Home, Recommendations, deployment, or authentication.

## Acceptance criteria

- Answer options are comfortably tappable on narrow screens.
- Sticky Next appears only after a saved answer and does not hide content.
- Desktop practice behavior and layout remain unchanged.

## Status

Implemented
