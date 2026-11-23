# Polish the Frontend Shell and Navigation

## Problem

The app has no persistent navigation and its global title scale is too large for
a calm, professional study interface.

## Desired behavior

Provide a responsive route-aware navigation bar and a restrained editorial
visual hierarchy while keeping Practice visually focused.

## Scope

- Add a shared header with desktop and mobile navigation.
- Refine typography, surfaces, spacing, and active navigation states.
- Remove redundant back-home links from normal page content.

## Constraints

- Preserve all app behavior, including the mobile floating Next control.
- Do not add dependencies or change backend behavior.

## Acceptance criteria

- Every primary route is reachable from the header and visibly active.
- Mobile navigation remains usable without hidden menu state.
- Titles are smaller and hierarchy remains clear.
- Practice navigation is present but subdued.

## Status

Implemented
