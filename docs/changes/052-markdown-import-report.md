# Convert the Import Report to Markdown

## Problem

The generated plain-text import report is difficult to navigate when reviewing
large content-health and morphology sections in an editor.

## Desired behavior

Generate `data/import-report.md` with navigable Markdown headings while
preserving all existing report content. The separate Tatoeba extraction audit
remains a text report.

## Scope

- Render report sections as Markdown headings and findings as lists.
- Update the pipeline output path, CLI guidance, tests, and documentation.

## Acceptance criteria

- Normal, dry-run, and validation-failure imports write `data/import-report.md`.
- VS Code can navigate the report's major sections through its Markdown outline.
- The report retains every existing summary, finding, diagnostic, and error.

## Status

Implemented
