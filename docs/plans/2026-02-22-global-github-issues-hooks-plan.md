# Global GitHub Issues Hooks — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move GitHub Issues tracking to global level and add SessionStart hook to show open issues at session start.

**Architecture:** Two global hooks (SessionStart + PostToolUse) in `~/.claude/settings.json`, instructions in `~/.claude/CLAUDE.md`, cleanup of project-level duplicates in teleshelf.

**Tech Stack:** Bash/sh scripts, jq, gh CLI, Claude Code hooks API

---

### Task 1: Create global SessionStart hook script

**Files:**
- Create: `~/.claude/hooks/gh-issues-start.sh`

**Step 1: Write the script**

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

**Step 2: Make it executable**

Run: `chmod +x ~/.claude/hooks/gh-issues-start.sh`

**Step 3: Verify the script runs without error**

Run: `~/.claude/hooks/gh-issues-start.sh`
Expected: Either list of issues or "No open GitHub issues" message (depending on current repo state). Exit code 0.

---

### Task 2: Create global PostToolUse hook script

**Files:**
- Create: `~/.claude/hooks/close-issue-on-commit.sh` (copy from project-level)

**Step 1: Copy the existing script**

```bash
cp /Users/alexeyprudkin/dev/teleshelf/.claude/hooks/close-issue-on-commit.sh ~/.claude/hooks/close-issue-on-commit.sh
chmod +x ~/.claude/hooks/close-issue-on-commit.sh
```

**Step 2: Verify the script is valid**

Run: `echo '{"tool_input":{"command":"echo hello"}}' | ~/.claude/hooks/close-issue-on-commit.sh; echo "exit: $?"`
Expected: exit: 0 (no output, since "echo hello" doesn't match "git commit")

---

### Task 3: Update global `~/.claude/settings.json`

**Files:**
- Modify: `~/.claude/settings.json`

**Step 1: Add SessionStart hook entry (second element in array)**

Add a new entry to the existing `SessionStart` array, after the osgrep hook:

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "/Users/alexeyprudkin/.claude/hooks/gh-issues-start.sh",
      "timeout": 15
    }
  ]
}
```

**Step 2: Add PostToolUse hook section**

Add new `PostToolUse` key to the `hooks` object:

```json
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
```

**Step 3: Verify JSON is valid**

Run: `python3 -m json.tool ~/.claude/settings.json > /dev/null && echo "valid" || echo "INVALID"`
Expected: valid

The final `hooks` section should look like:

```json
"hooks": {
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/Users/alexeyprudkin/.claude/hooks/osgrep-start.sh",
          "timeout": 10
        }
      ]
    },
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
  ],
  "SessionEnd": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/Users/alexeyprudkin/.claude/hooks/osgrep-end.sh",
          "timeout": 30
        }
      ]
    }
  ]
}
```

---

### Task 4: Add GitHub Issue Tracking section to global `~/.claude/CLAUDE.md`

**Files:**
- Modify: `~/.claude/CLAUDE.md` (add section before "Workflow Orchestration", after "Obsidian Vault")

**Step 1: Add the section**

Insert after the `## Obsidian Vault` section (after line 145) and before `## Workflow Orchestration`:

```markdown
---

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

**Step 2: Sync via chezmoi**

Run: `chezmoi re-add ~/.claude/CLAUDE.md && chezmoi git -- add -A && chezmoi git -- commit -m "chore: add GitHub Issue Tracking to global Claude instructions"`

---

### Task 5: Clean up teleshelf project-level files

**Files:**
- Delete: `teleshelf/.claude/hooks/close-issue-on-commit.sh`
- Modify: `teleshelf/.claude/settings.json` (remove PostToolUse hook)
- Modify: `teleshelf/CLAUDE.md` (remove GitHub Issue Tracking section)

**Step 1: Remove the project-level hook script**

Run: `rm /Users/alexeyprudkin/dev/teleshelf/.claude/hooks/close-issue-on-commit.sh`

**Step 2: Update project settings.json**

Replace the entire content of `teleshelf/.claude/settings.json` with:

```json
{}
```

(The file had only the PostToolUse hook; with that removed, it's empty.)

**Step 3: Remove GitHub Issue Tracking section from teleshelf/CLAUDE.md**

Remove lines 241-268 (the `## GitHub Issue Tracking` section including the `---` separator before it).

The file should end with:

```markdown
- **Reader output:** `reader/index.html` — combined reader for all channels

---

*Updated: 2026-02-22*
```

**Step 4: Verify CLAUDE.md ends cleanly**

Run: `tail -5 /Users/alexeyprudkin/dev/teleshelf/CLAUDE.md`
Expected: Should show the "Reader output" line, a separator, and the Updated date — no GitHub Issue Tracking section.

---

### Task 6: Sync settings.json via chezmoi

**Step 1: Re-add settings.json to chezmoi**

Run: `chezmoi re-add ~/.claude/settings.json && chezmoi git -- add -A && chezmoi git -- commit -m "chore: add global GitHub Issues hooks to settings.json"`

---

### Task 7: Commit teleshelf cleanup

**Step 1: Stage and commit the project-level changes**

```bash
cd /Users/alexeyprudkin/dev/teleshelf
git add .claude/settings.json .claude/hooks/ CLAUDE.md
git commit -m "chore: move GitHub Issues hooks to global config

Hooks and instructions now live in ~/.claude/ and apply to all
GitHub repos. Removed project-level duplicates.
"
```

---

### Task 8: Verify end-to-end

**Step 1: Verify global hooks are registered**

Run: `cat ~/.claude/settings.json | python3 -m json.tool | grep -A2 "gh-issues-start\|close-issue-on-commit"`
Expected: Both hook paths appear in valid JSON.

**Step 2: Verify scripts are executable**

Run: `ls -la ~/.claude/hooks/gh-issues-start.sh ~/.claude/hooks/close-issue-on-commit.sh`
Expected: Both files have execute permission (-rwx...).

**Step 3: Verify SessionStart script output**

Run: `cd /Users/alexeyprudkin/dev/teleshelf && ~/.claude/hooks/gh-issues-start.sh`
Expected: Either issue list or "No open GitHub issues" message.

**Step 4: Verify project-level hook is removed**

Run: `cat /Users/alexeyprudkin/dev/teleshelf/.claude/settings.json`
Expected: `{}`

**Step 5: Verify CLAUDE.md has no GitHub Issue section**

Run: `grep -c "GitHub Issue Tracking" /Users/alexeyprudkin/dev/teleshelf/CLAUDE.md`
Expected: 0

**Step 6: Verify global CLAUDE.md has the section**

Run: `grep -c "GitHub Issue Tracking" ~/.claude/CLAUDE.md`
Expected: 1
