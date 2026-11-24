# Polish Mobile Layout

## Problem

The application is responsive, but its phone layout needs a final usability
pass. In particular, the floating arrow-only Next control obscures the familiar
desktop action and long content can crowd narrow layouts.

## Desired behavior

All pages remain comfortable at phone widths. Navigation stays horizontally
scrollable, and Practice uses the same labelled Next button as desktop.

## Scope

- Refine responsive spacing, wrapping, and touch layouts across all pages.
- Make the mobile navigation row visibly separate and easy to scroll.
- Replace the fixed circular Next arrow with an in-flow labelled button for
  answer feedback and sentence breaks.

## Constraints

- Keep desktop layout, APIs, quiz behavior, and content data unchanged.
- Do not replace navigation with a menu or change the existing routes.

## Acceptance criteria

- At 320px, 375px, and 430px wide, navigation, cards, actions, and long text
  remain visible and usable without horizontal page overflow.
- Practice feedback and reading breaks show an in-flow labelled Next button.
- Existing desktop practice behavior is unchanged.

## Status

Implemented
