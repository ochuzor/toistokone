
# ToistoKone — Codex Instructions

## Project

ToistoKone is a local-first Finnish vocabulary and word-form
practice application.

Tech stack:
- Frontend: React + Vite + React Router
- Backend: Python + FastAPI
- Databases: SQLite (separate content and progress databases)

ToistoKone v1 has been implemented. The project is now in
the iterative improvement and maintenance phase.

## Project Documentation

The following documents describe the original application:

1. `docs/toistokone_prd.md`
2. `docs/toistokone_technical_spec.md`
3. `docs/toistokone_implementation_plan.md`

The PRD is the source of truth for existing product behavior.
The Technical Specification describes the architecture.

The original Implementation Plan is complete and retained
for historical reference. Do not execute its phases again.

Ongoing development uses:

- `docs/BACKLOG.md` — Prioritized improvement ideas.
- `docs/changes/` — Specifications for individual changes.

Read the relevant documentation and inspect existing code
before proposing or implementing changes.

If a requested change conflicts with existing documentation,
identify the conflict and propose the necessary updates.

## Development Workflow

For new improvements and features:

1. Understand the requested change.
2. Inspect the relevant code and documentation.
3. Identify affected components, dependencies, and risks.
4. For non-trivial changes, create a concise specification
   in `docs/changes/`.
5. Present the proposed approach and wait for approval
   before implementing non-trivial changes.
6. Implement only the approved scope.
7. Add or update relevant automated tests.
8. Run tests and verify UI behavior with Playwright MCP
   when applicable.
9. Update relevant documentation when behavior or
   architecture changes.
10. Report the results and any remaining issues.

For small bug fixes, typos, styling adjustments, or
straightforward maintenance tasks, implement directly
unless explicitly instructed otherwise.

Do not introduce unrelated refactoring or scope expansion.

### Change Specifications

Use descriptive filenames such as:

`docs/changes/001-improve-quiz-feedback.md`

Each specification should contain:

- Problem
- Desired behavior
- Scope
- Constraints
- Acceptance criteria
- Status

Keep specifications concise and proportional to the
complexity of the change.

Update the change status when implementation is completed.

### Backlog

Use `docs/BACKLOG.md` to track improvement ideas.

Organize items into:
- Next
- Later
- Completed

Update the backlog when a tracked improvement is completed.

Do not implement backlog items unless explicitly requested.

## MCP Tools

MCP servers are configured in `.codex/config.toml`.

Use them when appropriate.

### Context7

Consult current library documentation when implementing
React, Vite, FastAPI, Pydantic, or other dependencies,
especially for version-specific behavior.

### SQLite

Inspect local databases when debugging schemas, queries,
imports, and mastery tracking.

Two SQLite MCP connections are configured:

- `sqlite_content`: Generated vocabulary, word forms,
  and example sentences.
- `sqlite_progress`: Persistent mastery scores and
  practice history.

Use the appropriate connection when inspecting data.

The content database may be rebuilt by the import pipeline.

The progress database must never be deleted, replaced,
or reset by the import pipeline.

Prefer read-only SQL queries for inspection.

### Playwright

Use browser automation to verify relevant UI behavior,
including:

- Navigation between Home and Practice
- Quiz interactions and answer feedback
- Mastery score updates
- Practice queue persistence
- Automatic queue replenishment
- New or modified UI functionality

If an MCP server is unavailable, report the issue rather
than assuming it works.

## Development Rules

- Keep implementations minimal, readable, and maintainable.
- Preserve existing behavior unless a change explicitly
  requires modifying it.
- Preserve the mastery and quiz selection algorithms unless
  their modification is explicitly approved.
- Keep content and progress databases separate.
- Never modify progress data during content imports.
- Use `npm run dev` to start frontend and backend.
- Write and run relevant automated tests.
- Fix failing tests introduced by the change.
- Do not introduce Docker, authentication, PostgreSQL,
  cloud services, or AI-generated sentences unless
  explicitly requested and approved.
- Avoid unnecessary dependencies and abstractions.
- Do not make unrelated changes.

## Testing

For each change:

1. Run relevant unit and integration tests.
2. Add regression tests for bug fixes when practical.
3. Use Playwright MCP for browser-facing changes.
4. Verify that existing functionality remains intact.
5. Report any tests that could not be executed.

Never claim tests passed unless they were actually run.

## Reporting

After completing a change, report:

- Summary of the implementation
- Files created or modified
- Tests executed and their results
- Documentation updated
- Any unresolved issues or follow-up recommendations

For non-trivial changes, stop after proposing the
implementation approach and wait for approval.

Do not automatically begin additional improvements.
