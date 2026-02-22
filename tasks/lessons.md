# Lessons

## 2026-02-22 — WebFetch returns summaries, not full article content

- **Failure mode:** WebFetch summarizes aggressively — 3 attempts to get full blog article content all returned condensed summaries with missing code blocks and details
- **Detection signal:** WebFetch result is noticeably shorter than expected, missing code blocks or configuration examples that should be present
- **Prevention rule:** When WebFetch returns incomplete content (summaries instead of full text), stop retrying and ask the user whether to try firecrawl or another approach. Do not repeat WebFetch with rephrased prompts — the tool inherently summarizes.
