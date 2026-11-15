
# ToistoKone — Codex Instructions

## Project

ToistoKone is a local-first Finnish vocabulary and word-form
practice application.

Tech stack:
- Frontend: React + Vite + React Router
- Backend: Python + FastAPI
- Databases: SQLite (separate content and progress databases)

## Project Documentation

Read these documents before implementing features:

1. docs/toistokone_prd_draft.md
2. docs/toistokone_technical_spec_draft.md
3. docs/toistokone_implementation_plan_draft.md

The PRD is the source of truth for product behavior.

Follow the implementation plan sequentially. Complete and test
each phase before proceeding to the next.

Do not start a new phase without explicit approval.

## MCP Tools

MCP servers are configured in `.codex/config.toml`.

Use them when appropriate:

### Context7
Consult current library documentation when implementing
React, Vite, FastAPI, Pydantic, or other dependencies.

### SQLite
Inspect local databases when debugging schemas, queries,
imports, and mastery tracking.

Never overwrite or reset the progress database during
content imports.


#### SQLite MCP Servers

Two SQLite MCP connections are available:

- `sqlite_content`: Generated vocabulary, word forms,
  and example sentences.
- `sqlite_progress`: Persistent mastery scores and
  practice history.

Use the appropriate connection when inspecting data.

The content database may be rebuilt by the import pipeline.

The progress database must never be deleted, replaced,
or reset by the import pipeline.

Use read-only SQL queries for inspection whenever possible.


### Playwright
Use browser automation to verify:
- Navigation between Home and Practice
- Quiz interactions and answer feedback
- Mastery score updates
- Practice queue persistence
- Automatic queue replenishment

If an MCP server is unavailable, report it rather than
assuming it works.

## Development Rules

- Keep implementations minimal and maintainable.
- Do not introduce features outside the PRD.
- Preserve the exact mastery and quiz selection algorithms.
- Keep content and progress databases separate.
- Use `npm run dev` to start frontend and backend.
- Write and run relevant automated tests.
- Fix failing tests before reporting a phase complete.
- Do not introduce Docker, authentication, PostgreSQL,
  cloud services, or AI-generated sentences.

## Reporting

After each implementation phase, report:
- What was implemented
- Files created or modified
- Tests run and their results
- Any unresolved issues

Stop and wait for approval before starting the next phase.
