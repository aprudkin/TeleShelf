# GitHub Issue Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically track every non-trivial Claude Code task as a GitHub issue — created at the start of work, closed when a commit is made.

**Architecture:** CLAUDE.md instruction tells Claude to create a GitHub issue before non-trivial tasks. A PostToolUse hook script detects `git commit` commands and auto-closes the referenced issue number.

**Tech Stack:** Shell script (zsh-compatible), `gh` CLI, `jq`, Claude Code hooks (`.claude/settings.json`)

---

### Task 1: Create the hook script

**Files:**
- Create: `.claude/hooks/close-issue-on-commit.sh`

**Step 1: Create hooks directory**

Run: `mkdir -p /Users/alexeyprudkin/dev/teleshelf/.claude/hooks`

**Step 2: Write the hook script**

Create `.claude/hooks/close-issue-on-commit.sh`:

```bash
#!/bin/sh
# PostToolUse hook: closes GitHub issues referenced in git commit messages.
# Triggered on every Bash tool use; filters for git commit commands.
# Always exits 0 to avoid blocking the workflow.

INPUT=$(cat)

# Only act on git commit commands
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
case "$COMMAND" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

# Extract issue numbers from "Closes #N" patterns in the commit command
ISSUES=$(echo "$COMMAND" | grep -oE '[Cc]loses #[0-9]+' | grep -oE '[0-9]+')

if [ -z "$ISSUES" ]; then
  exit 0
fi

# Close each referenced issue
for ISSUE_NUM in $ISSUES; do
  gh issue close "$ISSUE_NUM" --comment "Closed automatically by Claude Code commit hook." 2>/dev/null || true
done

exit 0
```

**Step 3: Make script executable**

Run: `chmod +x /Users/alexeyprudkin/dev/teleshelf/.claude/hooks/close-issue-on-commit.sh`

**Step 4: Verify script is executable**

Run: `ls -la /Users/alexeyprudkin/dev/teleshelf/.claude/hooks/close-issue-on-commit.sh`
Expected: `-rwxr-xr-x` permissions

**Step 5: Smoke-test the script with mock input**

Run:
```bash
echo '{"tool_input":{"command":"git commit -m \"feat: test Closes #999\""}}' | /Users/alexeyprudkin/dev/teleshelf/.claude/hooks/close-issue-on-commit.sh
echo "Exit code: $?"
```
Expected: Exit code 0, no errors (gh issue close will fail silently since #999 doesn't exist)

Run (non-commit command — should exit immediately):
```bash
echo '{"tool_input":{"command":"ls -la"}}' | /Users/alexeyprudkin/dev/teleshelf/.claude/hooks/close-issue-on-commit.sh
echo "Exit code: $?"
```
Expected: Exit code 0, no output

---

### Task 2: Create the hook configuration

**Files:**
- Create: `.claude/settings.json`

**Step 1: Write settings.json**

Create `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/close-issue-on-commit.sh"
          }
        ]
      }
    ]
  }
}
```

Note: This file is separate from `.claude/settings.local.json` (which holds personal permissions). `settings.json` is committable and shared; `settings.local.json` stays gitignored and personal.

**Step 2: Verify JSON is valid**

Run: `jq . /Users/alexeyprudkin/dev/teleshelf/.claude/settings.json`
Expected: Pretty-printed JSON output with no errors

---

### Task 3: Add issue tracking instructions to CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (append before the final `*Updated:` line)

**Step 1: Add the GitHub Issue Tracking section**

Append this section to `CLAUDE.md` before the `*Updated:` footer (after the Conventions section, before line 243):

```markdown
## GitHub Issue Tracking

Every non-trivial task must be tracked as a GitHub issue.

### When to create an issue
- Features, bugfixes, refactors — anything that will result in a commit
- Skip for: questions, research, exploration, trivial one-line fixes, brainstorming sessions

### How to create
```bash
gh issue create --title "<imperative English title, <70 chars>" --body "<1-3 bullet points describing scope>"
```

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

**Step 2: Update the `*Updated:` date**

Change `*Updated: 2026-02-21*` to `*Updated: 2026-02-22*`

**Step 3: Verify CLAUDE.md is well-formed**

Run: `wc -l /Users/alexeyprudkin/dev/teleshelf/CLAUDE.md`
Expected: ~270 lines (was 243, added ~25)

---

### Task 4: End-to-end verification

**Step 1: Create a test issue**

Run: `gh issue create --title "Test: verify issue tracking hook" --body "Automated test — will be closed immediately." --repo aprudkin/TeleShelf`
Note the issue number from output.

**Step 2: Test the hook script with real issue**

Run (replace N with the actual issue number):
```bash
echo '{"tool_input":{"command":"git commit -m \"test: verify hook Closes #N\""}}' | /Users/alexeyprudkin/dev/teleshelf/.claude/hooks/close-issue-on-commit.sh
```

**Step 3: Verify issue was closed**

Run: `gh issue view N --repo aprudkin/TeleShelf`
Expected: State shows "CLOSED"

**Step 4: Clean up test issue** (optional)

Run: `gh issue delete N --repo aprudkin/TeleShelf --yes`

---

### Task 5: Commit all changes

**Step 1: Stage files**

```bash
git add .claude/settings.json .claude/hooks/close-issue-on-commit.sh CLAUDE.md docs/plans/2026-02-22-github-issue-tracking-design.md
```

**Step 2: Commit**

```bash
git commit -m "feat: add GitHub issue tracking via CLAUDE.md + PostToolUse hook

- Add CLAUDE.md instruction for creating issues on non-trivial tasks
- Add PostToolUse hook script to auto-close issues on git commit
- Add .claude/settings.json with hook configuration
- Add design document

Closes #N"
```

(Replace `#N` with the issue number if one was created for this task itself.)
