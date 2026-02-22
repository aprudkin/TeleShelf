# Lessons

## 2026-02-22 — WebFetch returns summaries, not full article content

- **Failure mode:** WebFetch summarizes aggressively — 3 attempts to get full blog article content all returned condensed summaries with missing code blocks and details
- **Detection signal:** WebFetch result is noticeably shorter than expected, missing code blocks or configuration examples that should be present
- **Prevention rule:** When WebFetch returns incomplete content (summaries instead of full text), stop retrying and ask the user whether to try firecrawl or another approach. Do not repeat WebFetch with rephrased prompts — the tool inherently summarizes.

## 2026-02-22 — GitHub issue must be created BEFORE first commit

- **Failure mode:** Started brainstorming/design, committed design doc and plan without creating a GitHub issue first. Two commits landed without `Closes #N`. Issue was only created after user reminded.
- **Detection signal:** About to run `git commit` on a non-trivial task and no `gh issue create` has been run yet in this session.
- **Prevention rule:** For any non-trivial task, create the GitHub issue as the FIRST action — before any exploration, design, or commits. Note the issue number immediately. Include `Closes #N` in every commit message. This is a hard gate: no commit without an issue number.

## 2026-02-22 — Taskfile is for end users, not developer tooling

- **Failure mode:** Proposed adding `task release` (version bump + Homebrew formula update) to the project Taskfile.yml. User corrected: Taskfile commands are for end users syncing channels and building the reader, not for CI/release/developer workflows.
- **Detection signal:** About to add a task to Taskfile.yml that doesn't involve channel sync, reader, or content operations.
- **Prevention rule:** Taskfile.yml tasks must be user-facing operations only (sync, build-reader, add-channel, re-export). Developer/CI automation (releases, formula updates, linting) goes in GitHub Actions workflows or global ~/Taskfile.yml.
