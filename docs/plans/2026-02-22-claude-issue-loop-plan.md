# Claude Issue Loop — Implementation Plan

**Date:** 2026-02-22
**Design:** [claude-issue-loop-design.md](2026-02-22-claude-issue-loop-design.md)

## Steps

### 1. Create script skeleton with arg parsing

**File:** `~/.claude/scripts/claude-issue-loop.sh`

Parse CLI flags:
- `--once` — process one issue, then stop
- `--dry-run` — print issues, don't process
- `--model <model>` — override default model (default: `claude-sonnet-4-6`)
- `--max-parallel <N>` — max concurrent jobs (default: 3)

Validate prerequisites:
- Inside a git repo (`git rev-parse --git-dir`)
- Has GitHub remote (`gh repo view --json name`)
- `claude` CLI available (`command -v claude`)

**Verify:** Script runs, prints help with `--help`, exits cleanly with `--dry-run` when no `todo` issues exist.

### 2. Implement issue fetching and dry-run

Fetch issues labeled `todo`:
```bash
gh issue list --label "todo" --state open --json number,title,body --limit 20
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

### 6. Implement single-issue processing function

`process_issue <number> <title> <body>`:

1. Label: `todo` → `in-progress`
2. Read `PROGRESS.md` from repo root (if exists)
3. Build prompt string with issue context + instructions
4. Run: `claude -p -w "issue-$NUMBER-$SLUG" --model "$MODEL" --allowedTools Bash,Read,Write,Edit,Glob,Grep,Task "$PROMPT"`
5. Capture exit code and stdout (summary)
6. On success:
   - Push worktree branch: `git -C .claude/worktrees/issue-$N-$SLUG push -u origin HEAD`
   - Create PR: `gh pr create --head "worktree-issue-$N-$SLUG" --title "$TITLE" --body "Closes #$N\n\n$SUMMARY"`
   - Post summary comment to issue
   - Remove `in-progress` label
7. On failure:
   - Post error comment to issue
   - Remove `in-progress` label
8. Append to `PROGRESS.md`

**Verify:** Process a single test issue with `--once`. Confirm: worktree created, commits made, PR created, label removed, PROGRESS.md updated.

### 7. Implement parallel execution with concurrency limit

Main loop:
```bash
RUNNING=0
for issue in $ISSUES; do
  process_issue "$issue" &
  RUNNING=$((RUNNING + 1))
  if [ "$RUNNING" -ge "$MAX_PARALLEL" ]; then
    wait -n  # wait for any one job to finish
    RUNNING=$((RUNNING - 1))
  fi
done
wait  # wait for remaining jobs
```

Handle PROGRESS.md writes safely: each job writes to a temp file (`/tmp/claude-loop-$ISSUE_NUM.md`), main process merges them after `wait`.

**Verify:** Create 3 test issues with `todo` label. Run with `--max-parallel 2`. Confirm 2 run in parallel, third waits. All PRs created.

### 8. Implement worktree cleanup flag

Add `--cleanup` flag that removes completed worktrees:
```bash
~/.claude/scripts/claude-issue-loop.sh --cleanup
```

Lists worktrees in `.claude/worktrees/issue-*`, checks if the corresponding PR is merged/closed, removes with `git worktree remove`. Without `--cleanup`, worktrees accumulate (warn if > 5 exist).

**Verify:** After merging a PR, `--cleanup` removes its worktree. Unmerged PRs' worktrees are preserved.

### 9. Implement summary output

After all jobs complete, print:
```
=== Claude Issue Loop Summary ===
Processed: 3
  ✓ #5 — Add search to reader (PR #12)
  ✓ #8 — Fix pagination (PR #13)
  ✗ #11 — Refactor build system (error: timeout)
```

**Verify:** Output matches expected format after processing mixed success/failure issues.

### 10. Sync to chezmoi and test end-to-end

```bash
chezmoi add ~/.claude/scripts/claude-issue-loop.sh
chezmoi git -- add -A && chezmoi git -- commit -m "feat: add claude-issue-loop.sh"
```

End-to-end test in a real repo:
1. Create 2 issues with `todo` label
2. Run `~/.claude/scripts/claude-issue-loop.sh`
3. Verify: 2 PRs created, labels managed, PROGRESS.md updated

### 11. Add .claude/worktrees/ to .gitignore

Check if `.claude/worktrees/` is already in `.gitignore` for current repo. If not, add it.

**Verify:** Worktree directories don't show up in `git status`.

### 12. Write Obsidian article

**File:** `~/Obsidian/obsidian/30 Wiki/Claude Code — Issue Loop.md`

Check if an existing article covers this topic (e.g., the deleted `Claude Code — GitHub Issues Hooks.md` — it no longer exists). Create a new article from scratch.

Content structure:
- Frontmatter: title, created, updated, type: wiki, tags (claude, claude-code, automation, workflow, github)
- Overview: what the issue loop does and why (context rot, parallel execution, unattended work)
- Architecture diagram (text): issue lifecycle, label states, worktree flow
- Full annotated script walkthrough: each function with explanation
- CLI usage examples: `--once`, `--dry-run`, `--max-parallel`, `--model`
- PROGRESS.md format and rules
- Prerequisites (claude CLI, gh CLI, labels)
- Example end-to-end session: create issues → run loop → review PRs
- Design decisions: why worktrees, why labels, why sonnet default, why no hooks
- Links to related articles: Knowledge Layers, Superpowers Plugin Guide, Chezmoi

Commit changes to Obsidian vault.

**Verify:** Article renders correctly in Obsidian, all links resolve.
