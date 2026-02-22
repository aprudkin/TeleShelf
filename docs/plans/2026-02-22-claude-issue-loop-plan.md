# Claude Issue Loop — Implementation Plan

**Date:** 2026-02-22
**Design:** [claude-issue-loop-design.md](2026-02-22-claude-issue-loop-design.md)

## Steps

### 1. Create script skeleton with arg parsing

**File:** `~/.claude/scripts/claude-issue-loop.sh`

**Shebang:** `#!/opt/homebrew/bin/bash` — macOS ships bash 3.2 which does NOT support `wait -n` (requires bash 4.3+). Use Homebrew bash. Add a guard at the top:
```bash
if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 3))); then
  echo "Error: bash 4.3+ required (for wait -n). Install: brew install bash" >&2
  exit 1
fi
```

Parse CLI flags:
- `--once` — process one issue, then stop
- `--dry-run` — print issues, don't process
- `--model <model>` — override default model (default: `claude-sonnet-4-6`)
- `--max-parallel <N>` — max concurrent jobs (default: 3)
- `--timeout <seconds>` — per-issue timeout (default: 1800 = 30 min)
- `--cleanup` — remove worktrees for merged/closed PRs
- `--recover` — detect and fix stale `in-progress` labels

Validate prerequisites:
- Inside a git repo (`git rev-parse --git-dir`)
- Has GitHub remote (`gh repo view --json name`)
- `claude` CLI available (`command -v claude`)

**Verify:** Script runs, prints help with `--help`, exits cleanly with `--dry-run` when no `todo` issues exist.

### 2. Implement issue fetching and dry-run

Fetch issues labeled `todo` (including comments for additional context):
```bash
gh issue list --label "todo" --state open --json number,title,body,comments --limit 20
```

Sort by issue number ascending (oldest first).

For `--dry-run`: print each issue as `#N — title` and exit.

**Verify:** Create a test issue with `todo` label, confirm `--dry-run` lists it.

### 3. Implement label management helpers

Functions:
- `label_issue <number> <add-label> [remove-label]` — add/remove labels atomically
- `ensure_labels_exist` — create `todo` and `in-progress` labels if missing (via `gh label create --force`)

**Verify:** Labels appear on GitHub after running `ensure_labels_exist`.

### 4. Implement slugify and worktree naming

Function:
- `slugify <title>` — lowercase, spaces→hyphens, strip non-alnum, truncate to 50 chars
- Worktree name: `issue-<number>-<slug>`

**Verify:** Test with edge cases: unicode titles, very long titles, special characters.

### 5. Implement issue validation

Before processing, validate each issue:
- **Body length check:** reject issues with body < 50 chars — post a comment: "Issue body is too short. Add acceptance criteria, context, and expected behavior before labeling `todo`." Remove `todo` label.
- **Dependency parsing:** scan issue body for `blocked-by #N` or `depends-on #N` patterns. If the referenced issue is still open, skip this issue (leave `todo` label, print warning). This prevents parallel agents from working on dependent issues simultaneously.

**Verify:** Create an issue with short body — confirm it gets rejected with a comment. Create two issues where #2 has `blocked-by #1` — confirm #2 is skipped while #1 is open.

### 6. Implement prompt building via temp file

Build the prompt as a temp file instead of inline shell argument (avoids `ARG_MAX` limits with long issue bodies):

```bash
PROMPT_FILE=$(mktemp /tmp/claude-loop-prompt-XXXXXX.md)
cat > "$PROMPT_FILE" <<EOF
You are working on GitHub issue #$NUMBER in this repository.

## Issue
Title: $TITLE
Body:
$BODY

## Comments
$(format_comments "$COMMENTS")

## Cross-session context
$(cat "$REPO_ROOT/PROGRESS.md" 2>/dev/null || echo "No previous context.")

## Instructions
- You are in an isolated git worktree — commit freely
- Make atomic commits with clear messages
- Run tests/lint/build if the project has them
- When done, output a one-paragraph summary of what you did
EOF
```

Feed to claude. First verify how `claude -p` accepts prompt input:
```bash
# Test 1: stdin
echo "What is 2+2?" | claude -p
# Test 2: argument
claude -p "What is 2+2?"
# Test 3: file via subshell
claude -p "$(cat "$PROMPT_FILE")"
```

Use whichever method works. If stdin works, prefer it (cleanest for large prompts). If not, use `"$(cat ...)"` subshell.

Clean up temp file after use.

**Verify:** Create an issue with very long body (> 10KB). Confirm prompt file is created, claude receives full content, temp file is cleaned up.

### 7. Implement single-issue processing function

`process_issue <number> <title> <body>`:

1. Label: `todo` → `in-progress`
2. Build prompt file (step 6)
3. Run with timeout and per-job logging. First verify exact flag name (`claude --help` — may be `--allowedTools` or `--allowed-tools`):
   ```bash
   timeout "$TIMEOUT" claude -p -w "issue-$N-$SLUG" --model "$MODEL" \
     --allowedTools Bash,Read,Write,Edit,Glob,Grep,Task \
     < "$PROMPT_FILE" \
     > "$LOG_DIR/issue-$N.log" 2>&1
   ```
4. Capture exit code (124 = timeout, 0 = success, other = failure)
5. Extract summary: last paragraph from `$LOG_DIR/issue-$N.log`
6. Check if worktree has commits:
   ```bash
   WORKTREE_DIR=".claude/worktrees/issue-$N-$SLUG"
   COMMITS=$(git -C "$WORKTREE_DIR" rev-list --count HEAD ^"$(git rev-parse HEAD)" 2>/dev/null || echo "0")
   ```
   If `$COMMITS` is 0: treat as failure — post comment "Agent finished but made no changes", remove `in-progress` label, skip PR creation.
7. On success (exit 0 AND commits > 0):
   - Push worktree branch: `git -C .claude/worktrees/issue-$N-$SLUG push -u origin HEAD`
   - Create PR: `gh pr create --head "worktree-issue-$N-$SLUG" --title "$TITLE" --body "Closes #$N\n\n$SUMMARY"`
   - Post summary comment to issue
   - Remove `in-progress` label
8. On failure (exit non-zero, timeout, or no commits):
   - Post error comment to issue (include last 20 lines of log)
   - Remove `in-progress` label
9. Write structured result to `$LOG_DIR/issue-$N.json`:
   ```json
   {
     "issue": 5,
     "status": "success",
     "pr_url": "https://github.com/user/repo/pull/12",
     "duration_seconds": 342,
     "log_file": "/tmp/claude-loop-results/issue-5.log"
   }
   ```

**Note:** PROGRESS.md is read from the **main repo root** (`$REPO_ROOT`), not from the worktree. Each job writes a one-liner to `$LOG_DIR/issue-$N.progress`, merged into PROGRESS.md by the main process after all jobs finish.

**Verify:** Process a single test issue with `--once`. Confirm: worktree created, commits made, PR created, label removed, log file written, result JSON created.

### 8. Implement signal handling and cleanup trap

Add a `trap` handler for safe Ctrl+C / unexpected exit:

```bash
CHILD_PIDS=()

cleanup() {
  echo "Interrupted. Cleaning up..."
  # Kill all child processes
  for pid in "${CHILD_PIDS[@]}"; do
    kill "$pid" 2>/dev/null
  done
  # Remove in-progress labels from all issues that were being processed
  for num in "${IN_PROGRESS_ISSUES[@]}"; do
    gh issue edit "$num" --remove-label "in-progress" 2>/dev/null
  done
  exit 130
}

trap cleanup INT TERM EXIT
```

Track `CHILD_PIDS` and `IN_PROGRESS_ISSUES` arrays as jobs launch.

**Verify:** Start processing 2 issues, Ctrl+C mid-run. Confirm: child processes killed, `in-progress` labels removed, no orphaned jobs in `ps`.

### 9. Implement stale label recovery (--recover)

At startup (before main loop), check for stale `in-progress` labels:

```bash
gh issue list --label "in-progress" --state open --json number,title
```

For each stale issue:
- Check if a worktree exists: `.claude/worktrees/issue-$N-*`
  - If worktree exists with commits: warn "Issue #N has in-progress worktree. Run --cleanup or resume manually."
  - If no worktree: remove `in-progress` label, re-add `todo` label — this was a crashed run.

With `--recover` flag: automatically reset all stale `in-progress` → `todo`.

Without flag: print warnings and continue (don't touch stale issues).

**Verify:** Manually add `in-progress` label to an issue (simulating crash). Run with `--recover`. Confirm label is reset to `todo`.

### 10. Implement parallel execution with concurrency limit

Main loop:
```bash
RUNNING=0
for issue in $ISSUES; do
  process_issue "$issue" &
  CHILD_PIDS+=($!)
  IN_PROGRESS_ISSUES+=("$ISSUE_NUM")
  RUNNING=$((RUNNING + 1))
  if [ "$RUNNING" -ge "$MAX_PARALLEL" ]; then
    wait -n  # wait for any one job to finish
    RUNNING=$((RUNNING - 1))
  fi
done
wait  # wait for remaining jobs
```

After all jobs finish, merge per-job progress files into PROGRESS.md:
```bash
for f in "$LOG_DIR"/issue-*.progress; do
  cat "$f" >> "$REPO_ROOT/PROGRESS.md"
done
```

Prune PROGRESS.md if > 50 lines (remove oldest completed entries).

**Verify:** Create 3 test issues with `todo` label. Run with `--max-parallel 2`. Confirm 2 run in parallel, third waits. All PRs created. Logs are separate per job (not interleaved).

### 11. Implement worktree cleanup flag

Add `--cleanup` flag that removes completed worktrees:
```bash
~/.claude/scripts/claude-issue-loop.sh --cleanup
```

Lists worktrees in `.claude/worktrees/issue-*`, checks if the corresponding PR is merged/closed, removes with `git worktree remove`. Without `--cleanup`, worktrees accumulate (warn if > 5 exist).

**Verify:** After merging a PR, `--cleanup` removes its worktree. Unmerged PRs' worktrees are preserved.

### 12. Implement summary output

After all jobs complete, print:
```
=== Claude Issue Loop Summary ===
Processed: 3 (timeout: 30m each)
  ✓ #5 — Add search to reader (PR #12, 5m42s)
  ✓ #8 — Fix pagination (PR #13, 2m18s)
  ✗ #11 — Refactor build system (timeout after 30m)
Skipped: 1
  ⊘ #14 — Update API (blocked by #11)
Rejected: 1
  ⊘ #15 — Fix bug (body too short)

Logs: /tmp/claude-loop-results/
```

Read structured results from `$LOG_DIR/issue-*.json` to build the summary.

**Verify:** Output matches expected format after processing mixed success/failure/skip/reject issues.

### 13. Sync to chezmoi and test end-to-end

```bash
chezmoi add ~/.claude/scripts/claude-issue-loop.sh
chezmoi git -- add -A && chezmoi git -- commit -m "feat: add claude-issue-loop.sh"
```

End-to-end test in a **throwaway test repo** (not TeleShelf — avoid noise):
```bash
# Create test repo
mkdir /tmp/claude-loop-test && cd /tmp/claude-loop-test
git init && gh repo create claude-loop-test --private --source=. --push
echo "# Test" > README.md && git add . && git commit -m "init" && git push
```

Test scenarios:
1. Create 2 issues with `todo` label, run the loop — verify: 2 PRs created, labels managed, PROGRESS.md updated
2. Ctrl+C test: start a run, interrupt mid-processing — verify: child processes killed, `in-progress` labels removed
3. Recovery test: manually set `in-progress` label (simulate crash), run `--recover` — verify: label reset to `todo`
4. No-commits test: create issue that requires no code changes — verify: handled gracefully, no empty PR
5. Short body test: create issue with < 50 chars body — verify: rejected with comment

Clean up after testing:
```bash
gh repo delete claude-loop-test --yes
rm -rf /tmp/claude-loop-test
```

### 14. Add .claude/worktrees/ and PROGRESS.md to .gitignore

Check if `.claude/worktrees/` and `PROGRESS.md` are already in `.gitignore` for current repo. If not, add both:
```
.claude/worktrees/
PROGRESS.md
```

**Verify:** Neither worktree directories nor PROGRESS.md show up in `git status`.

### 15. Write Obsidian article

**File:** `~/Obsidian/obsidian/30 Wiki/Claude Code — Issue Loop.md`

Check if an existing article covers this topic (e.g., the deleted `Claude Code — GitHub Issues Hooks.md` — it no longer exists). Create a new article from scratch.

Content structure:
- Frontmatter: title, created, updated, type: wiki, tags (claude, claude-code, automation, workflow, github)
- Overview: what the issue loop does and why (context rot, parallel execution, unattended work)
- Architecture diagram (text): issue lifecycle, label states, worktree flow
- Full annotated script walkthrough: each function with explanation
- CLI usage examples: `--once`, `--dry-run`, `--max-parallel`, `--model`, `--timeout`, `--cleanup`, `--recover`
- PROGRESS.md format and rules
- Prerequisites (claude CLI, gh CLI, labels)
- Example end-to-end session: create issues → run loop → review PRs
- Troubleshooting: stale labels, orphaned worktrees, timeouts
- Design decisions: why worktrees, why labels, why sonnet default, why no hooks
- Links to related articles: Knowledge Layers, Superpowers Plugin Guide, Chezmoi

Commit changes to Obsidian vault.

**Verify:** Article renders correctly in Obsidian, all links resolve.
