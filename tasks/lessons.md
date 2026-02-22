# Lessons

## 2026-02-22 — WebFetch returns summaries, not full article content

- **Failure mode:** WebFetch summarizes aggressively — 3 attempts to get full blog article content all returned condensed summaries with missing code blocks and details
- **Detection signal:** WebFetch result is noticeably shorter than expected, missing code blocks or configuration examples that should be present
- **Prevention rule:** When WebFetch returns incomplete content (summaries instead of full text), stop retrying and ask the user whether to try firecrawl or another approach. Do not repeat WebFetch with rephrased prompts — the tool inherently summarizes.

## 2026-02-22 — Taskfile is for end users, not developer tooling

- **Failure mode:** Proposed adding `task release` (version bump + Homebrew formula update) to the project Taskfile.yml. User corrected: Taskfile commands are for end users syncing channels and building the reader, not for CI/release/developer workflows.
- **Detection signal:** About to add a task to Taskfile.yml that doesn't involve channel sync, reader, or content operations.
- **Prevention rule:** Taskfile.yml tasks must be user-facing operations only (sync, build-reader, add-channel, re-export). Developer/CI automation (releases, formula updates, linting) goes in GitHub Actions workflows or global ~/Taskfile.yml.
