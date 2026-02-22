# Global GitHub Issues Hooks — Design

**Date:** 2026-02-22
**Status:** Approved
**Scope:** Global (`~/.claude/`) — applies to all GitHub repos
**Reference:** https://sereja.tech/blog/claude-code-hooks-github-issues/

## Goal

Move GitHub Issues tracking from project-level (teleshelf) to global level. Add SessionStart hook to show open issues at session start. Make the workflow work automatically in any GitHub repo.

## Gap Analysis (Article vs Current Setup)

| Feature | Article | Current | Action |
|---------|---------|---------|--------|
| SessionStart: show open issues | Yes (in-progress label) | Missing | Add globally, no labels |
| PostToolUse: close on commit | Yes (on git push) | Project-level (on git commit, better) | Move to global |
| CLAUDE.md instructions | Not mentioned | Project-level only | Move to global |
| Labels (in-progress) | Yes | No | Skip (YAGNI) |

## Changes

### Create: `~/.claude/hooks/gh-issues-start.sh`

```bash
#!/bin/bash
# SessionStart hook: show open GitHub issues at session start.
# Only runs in GitHub repos. Plain text output for reliability.

CWD="${CLAUDE_PROJECT_DIR:-$PWD}"

# Skip if not a git repo or not on GitHub
if [ ! -d "$CWD/.git" ]; then
  exit 0
fi

cd "$CWD" || exit 0

# Check if this repo has a GitHub remote
gh repo view --json name >/dev/null 2>&1 || exit 0

# Fetch open issues
ISSUES=$(gh issue list --state open --limit 20 --json number,title,labels 2>/dev/null)

if [ -z "$ISSUES" ] || [ "$ISSUES" = "[]" ]; then
  echo "No open GitHub issues for this repo. Consider creating one for non-trivial tasks: gh issue create --title \"...\" --body \"...\""
  exit 0
fi

# Format as plain text
echo "Open GitHub issues for this repo:"
echo "$ISSUES" | jq -r '.[] | "  #\(.number) — \(.title)\(if (.labels | length) > 0 then " [\(.labels | map(.name) | join(", "))]" else "" end)"'
echo ""
echo "Pick up an issue or create a new one for your task."
```

### Create: `~/.claude/hooks/close-issue-on-commit.sh`

Moved from `teleshelf/.claude/hooks/close-issue-on-commit.sh` — no changes:

```bash
#!/bin/sh
# PostToolUse hook: closes GitHub issues referenced in git commit messages.
# Triggered on every Bash tool use; filters for git commit commands.
# Always exits 0 to avoid blocking the workflow.

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
case "$COMMAND" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

ISSUES=$(echo "$COMMAND" | grep -oE '[Cc]loses #[0-9]+' | grep -oE '[0-9]+')

if [ -z "$ISSUES" ]; then
  exit 0
fi

for ISSUE_NUM in $ISSUES; do
  gh issue close "$ISSUE_NUM" --comment "Closed automatically by Claude Code commit hook." 2>/dev/null || true
done

exit 0
```

### Update: `~/.claude/settings.json`

Add to `hooks` section:

```json
{
  "SessionStart": [
    { "existing osgrep hook" },
    {
      "hooks": [
        {
          "type": "command",
          "command": "/Users/alexeyprudkin/.claude/hooks/gh-issues-start.sh",
          "timeout": 15
        }
      ]
    }
  ],
  "PostToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "/Users/alexeyprudkin/.claude/hooks/close-issue-on-commit.sh"
        }
      ]
    }
  ]
}
```

### Update: `~/.claude/CLAUDE.md`

Add GitHub Issue Tracking section (moved from teleshelf/CLAUDE.md):

```markdown
## GitHub Issue Tracking

Every non-trivial task must be tracked as a GitHub issue.

### When to create an issue
- Features, bugfixes, refactors — anything that will result in a commit
- Skip for: questions, research, exploration, trivial one-line fixes, brainstorming sessions

### How to create
gh issue create --title "<imperative English title, <70 chars>" --body "<1-3 bullet points describing scope>"

### Commit convention
- Reference the issue in every commit message: `Closes #N`
- A PostToolUse hook automatically closes the issue when the commit runs

### Workflow
1. Evaluate if the task is non-trivial
2. Create a GitHub issue via `gh issue create`
3. Note the issue number
4. Implement the task
5. Include `Closes #N` in the commit message
6. Hook auto-closes the issue on commit
```

### Delete from teleshelf

- Remove `teleshelf/.claude/hooks/close-issue-on-commit.sh`
- Remove PostToolUse hook from `teleshelf/.claude/settings.json`
- Remove "GitHub Issue Tracking" section from `teleshelf/CLAUDE.md`

## Design Decisions

- **Plain text output** over JSON in SessionStart hook — more reliable per article's recommendation and known Claude Code bugs with JSON hook output
- **No labels** — YAGNI; showing all open issues is sufficient for personal projects
- **Trigger on git commit, not git push** — catches the issue reference earlier, works even if push happens later
- **Global scope** — GitHub Issues are useful in all repos, not just teleshelf
- **Always exit 0** — hooks must never block the workflow

## Post-Implementation

- Run `chezmoi re-add` for `~/.claude/CLAUDE.md` and `~/.claude/settings.json`
- Verify hooks work by starting a new Claude Code session in a GitHub repo
