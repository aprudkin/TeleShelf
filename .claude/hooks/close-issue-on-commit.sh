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
