# Claude Issue Loop — Design

**Date:** 2026-02-22
**Status:** Approved
**Location:** `~/.claude/scripts/claude-issue-loop.sh`
**Scope:** Global — works in any GitHub repo

## Goal

Autonomous agent loop that processes GitHub Issues without manual intervention. Fresh `claude -p` invocation per issue eliminates context rot. Label-based state management provides visibility. Each issue gets its own worktree and PR for safe, reviewable delivery. Parallel execution via `claude -p -w`.

## Inspiration

- [Linear-Driven Agent Loop](https://damiangalarza.com/posts/2026-02-13-linear-agent-loop/) — fresh invocations, issue-driven state machine
- [CCPM](https://github.com/automazeio/ccpm) — GitHub Issues as single source of truth, parallel agents
- [Claude Code Worktrees](https://code.claude.com/docs/en/common-workflows#subagent-worktrees) — native `--worktree` flag for isolated parallel sessions

## Architecture

```
claude-issue-loop.sh
  │
  ├─ gh issue list --label "todo" --json ...
  │   └─ Returns: [#5 "Add search", #8 "Fix pagination"]
  │
  ├─ For each issue (parallel via background jobs):
  │   │
  │   ├─ 1. Label: todo → in-progress
  │   ├─ 2. Read PROGRESS.md (if exists)
  │   ├─ 3. Build prompt with issue context
  │   ├─ 4. Run: claude -p -w issue-N-slug "$PROMPT" &
  │   │      └─ Creates worktree at .claude/worktrees/issue-N-slug/
  │   │      └─ Branch: worktree-issue-N-slug
  │   ├─ 5. Wait for claude to finish
  │   ├─ 6. Post summary comment to issue
  │   ├─ 7. Create PR from worktree branch: gh pr create
  │   ├─ 8. Label: in-progress → (remove)
  │   └─ 9. Update PROGRESS.md
  │
  └─ Summary: N processed, M failed
```

## Issue Lifecycle

```
[created] ──(user labels)──→ [todo] ──(loop picks up)──→ [in-progress]
                                                              │
                                                    claude -p works
                                                              │
                                                ┌─────────────┤
                                                │             │
                                           [PR created]  [failed]
                                                │             │
                                         (manual review)  (comment posted,
                                                │          label removed)
                                         [merged/closed]
```

### Labels

| Label | Color | Meaning |
|-------|-------|---------|
| `todo` | `#0E8A16` (green) | Ready for the loop to pick up |
| `in-progress` | `#FBCA04` (yellow) | Currently being processed by claude |

No `done` label — closing the issue (or merging the PR) is sufficient.

## Context Injection

Each `claude -p -w` invocation receives a structured prompt via a temp file (avoids `ARG_MAX` limits with long issue bodies):

```
You are working on GitHub issue #N in this repository.

## Issue
Title: <title>
Body:
<body>

## Comments
<issue comments, if any — may contain clarifications and additional context>

## Cross-session context
<contents of PROGRESS.md from main repo root, if exists>

## Instructions
- You are in an isolated git worktree — commit freely
- Make atomic commits with clear messages
- Run tests/lint/build if the project has them
- When done, output a one-paragraph summary of what you did
```

Prompt is written to a temp file and piped via stdin: `claude -p -w ... < /tmp/claude-loop-prompt-XXXXXX.md`. Temp file is cleaned up after use.

### Allowed tools

The `claude -p` invocation uses `--allowedTools` to grant:
- Bash, Read, Write, Edit, Glob, Grep, Task (subagents for exploration)

No interactive tools (AskUserQuestion) — the loop runs unattended.

### Timeout

Each `claude -p` invocation is wrapped in `timeout $TIMEOUT` (default: 1800s = 30 min). Exit code 124 = timed out. Configurable via `--timeout <seconds>`.

## PROGRESS.md — Cross-Session Memory

**Path:** `PROGRESS.md` in the project root (gitignored).

Written after each issue is processed. Read at the start of each invocation.

```markdown
# Progress

## Last updated: 2026-02-22 14:30

## Completed
- #5 Add search to reader — implemented full-text client-side search in reader.js
- #8 Fix pagination — fixed off-by-one in build_reader.py line 142

## Notes
- reader.js is 800+ lines, consider splitting
- build_reader.py uses jinja2 macros in templates/macros.html
```

**Rules:**
- Keep under 50 lines (compressed context, not raw history)
- Completed section: one line per issue with brief summary
- Notes section: persistent observations useful for future issues
- Old entries get pruned when file exceeds 50 lines (oldest completed items removed first)

## Git Strategy

Claude Code's `--worktree` flag handles branch creation and isolation natively:

1. `claude -p -w issue-N-<slug>` creates worktree at `.claude/worktrees/issue-N-<slug>/`
2. Branch `worktree-issue-N-<slug>` is auto-created from default remote branch
3. Claude works and commits inside the worktree
4. Script pushes branch and creates PR: `gh pr create`
5. Worktree is preserved (has commits) — cleaned up manually or after PR merge

### Worktree naming

`issue-<number>-<slugified-title>` — e.g., `issue-5-add-search-to-reader`

Slug: lowercase, spaces to hyphens, non-alphanumeric removed, truncated to 50 chars.

### Parallel execution

All `todo` issues launch as background jobs simultaneously:

```bash
claude -p -w issue-5-add-search "$PROMPT_5" &
claude -p -w issue-8-fix-pagination "$PROMPT_8" &
wait  # wait for all to finish
```

Each worktree is fully isolated — no conflicts between parallel agents. The `--max-parallel N` flag limits concurrency (default: 3).

### Per-job logging

Each job writes to its own log file and result JSON to avoid interleaved output:
- Log: `$LOG_DIR/issue-N.log` (full claude output)
- Result: `$LOG_DIR/issue-N.json` (status, PR URL, duration, error)
- Progress: `$LOG_DIR/issue-N.progress` (one-liner merged into PROGRESS.md after all jobs)

`$LOG_DIR` defaults to `/tmp/claude-loop-results/` (recreated each run).

## Issue Validation

Before processing, each issue is validated:

| Check | Behavior |
|-------|----------|
| Body < 50 chars | Reject: post comment asking for acceptance criteria, remove `todo` label, skip |
| `blocked-by #N` / `depends-on #N` in body | If referenced issue is still open, skip (leave `todo` label, log warning) |

This prevents wasted tokens on vague issues and avoids parallel conflicts on dependent issues.

## Worktree Cleanup

Worktrees accumulate in `.claude/worktrees/issue-*` after processing. The `--cleanup` flag removes completed ones:

```bash
~/.claude/scripts/claude-issue-loop.sh --cleanup
```

Checks each `issue-*` worktree: if the corresponding PR is merged/closed, removes with `git worktree remove`. Warns if > 5 worktrees exist without `--cleanup`.

## Signal Handling

Ctrl+C or unexpected exit triggers a `trap` handler that:
1. Kills all child `claude -p` processes
2. Removes `in-progress` labels from all issues being processed
3. Exits with code 130

This prevents orphaned background jobs and stale labels.

## Stale Label Recovery

If the script crashes mid-run, issues can be left with `in-progress` label and no PR. The `--recover` flag handles this:

```bash
~/.claude/scripts/claude-issue-loop.sh --recover
```

At startup, checks for `in-progress` labeled issues:
- If worktree exists with commits: warn (manual intervention needed)
- If no worktree: reset label `in-progress` → `todo` (crashed run, safe to retry)

Without `--recover`: prints warnings but doesn't touch stale issues.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `claude -p` exits non-zero | Post error comment (last 20 log lines) to issue, remove `in-progress` label, continue |
| `claude -p` times out (exit 124) | Same as non-zero, comment notes "timed out after Ns" |
| `gh` commands fail | Log warning, continue (best-effort) |
| No `todo` issues | Print "No issues to process", exit 0 |
| Not a git repo | Exit 1 with error message |
| Not a GitHub repo | Exit 1 with error message |
| Worktree already exists | Skip issue with warning (likely already in progress) |
| Issue body too short | Reject with comment, remove `todo` label |
| Blocked by open issue | Skip, leave `todo` label |
| Ctrl+C / SIGTERM | Kill children, remove `in-progress` labels, exit 130 |
| Stale `in-progress` labels | Warn at startup; `--recover` resets to `todo` |
| Agent made no commits | Post "no changes" comment, remove `in-progress`, skip PR creation |

The loop is resilient — one failed issue does not stop processing of remaining issues.

## CLI Interface

```bash
# Process all 'todo' issues (parallel, max 3 concurrent)
~/.claude/scripts/claude-issue-loop.sh

# Limit concurrency
~/.claude/scripts/claude-issue-loop.sh --max-parallel 5

# Process only one issue (oldest 'todo'), then stop
~/.claude/scripts/claude-issue-loop.sh --once

# Dry run — show what would be processed
~/.claude/scripts/claude-issue-loop.sh --dry-run

# Custom model (default: claude-sonnet-4-6)
~/.claude/scripts/claude-issue-loop.sh --model claude-opus-4-6

# Sequential mode (no parallelism)
~/.claude/scripts/claude-issue-loop.sh --max-parallel 1

# Clean up worktrees for merged/closed PRs
~/.claude/scripts/claude-issue-loop.sh --cleanup

# Custom timeout per issue (default: 30 min)
~/.claude/scripts/claude-issue-loop.sh --timeout 3600

# Fix stale in-progress labels from crashed runs
~/.claude/scripts/claude-issue-loop.sh --recover
```

### Default model

`claude-sonnet-4-6` — fast and cheap for autonomous work. Override with `--model` for complex issues.

## Prerequisites

- **bash 4.3+** — required for `wait -n`. macOS ships bash 3.2; install via `brew install bash` (`/opt/homebrew/bin/bash`). Script checks version at startup and exits with error if too old.
- `claude` CLI installed and authenticated
- `gh` CLI installed and authenticated
- Must be run from a git repo with a GitHub remote
- Issues must be labeled `todo` to be picked up

## What This Does NOT Do

- **No hooks** — this is a standalone script, not integrated into Claude Code's hook system
- **No auto-merge** — PRs require manual review and merge
- **No auto-labeling** — user manually labels issues as `todo`
- **No scheduled execution** — user runs the script manually (cron/launchd is a future enhancement)

## Future Enhancements (Not In Scope)

- Subagent code review before PR creation
- Scheduled execution via launchd/cron
- Slack/Telegram notification on completion
- Auto-label issues based on content (triage agent)
