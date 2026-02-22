# Smart add-channel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `task add-channel` accept just a URL, auto-deriving the slug from the Telegram username with interactive confirmation.

**Architecture:** Replace the 2-arg parsing block in the Taskfile `add-channel` task with smart detection: if 1 arg looks like a URL, parse it and derive slug from username (public) or error (private). Keep 2-arg form for private URLs. Prompt user to confirm/override the derived slug.

**Tech Stack:** go-task (Taskfile.yml), zsh, python3 (inline URL parsing)

---

### Task 1: Rewrite argument parsing in Taskfile.yml

**Files:**
- Modify: `Taskfile.yml:7-45` (add-channel task summary + argument parsing block)

**Step 1: Update the task summary/help text**

Replace lines 9-27 of `Taskfile.yml` with updated usage docs:

```yaml
    summary: |
      Usage: task add-channel -- <url>
             task add-channel -- <slug> <url>

      Creates the directory structure and channel.json for a new Telegram channel export.
      Accepts any Telegram post URL and resolves IDs automatically.

      For public channels (t.me/<username>/...), the slug is auto-derived from the
      username. You'll be prompted to confirm or override it.

      For private channels (t.me/c/<id>/...), you must provide the slug explicitly.

      Supported URL formats:
        Public:  https://t.me/<username>/<post-id>
        Private: https://t.me/c/<channel-id>/<post-id>
        With comments: append ?comment=<id> to auto-detect discussion group

      Examples:
        task add-channel -- "https://t.me/seeallochnaya/3412"
        task add-channel -- "https://t.me/somechannel/42?comment=100"
        task add-channel -- my-channel "https://t.me/c/1234567890/154"
```

**Step 2: Replace argument parsing block**

Replace lines 32-44 (from `ARGS=` through the slug regex check) with this new logic:

```bash
      ARGS=({{.CLI_ARGS}})
      ARG1="${ARGS[0]:-}"
      ARG2="${ARGS[1]:-}"

      if [[ -z "$ARG1" ]]; then
        echo "Error: URL is required."
        echo "Usage: task add-channel -- <url>"
        echo "       task add-channel -- <slug> <url>"
        exit 1
      fi

      # Detect if ARG1 is a URL or a slug
      if [[ "$ARG1" =~ ^https?:// ]]; then
        # Single arg: URL only — derive slug from username
        URL="$ARG1"

        # Check if public URL to extract username
        DERIVED_SLUG=$(python3 -c "
        import re, sys
        url = sys.argv[1]
        m = re.match(r'https?://t\.me/([a-zA-Z][a-zA-Z0-9_]{3,})/(\d+)', url)
        if m:
            # Convert username to slug: lowercase, replace _ with -
            print(m.group(1).lower().replace('_', '-'))
        else:
            print('')
        " "$URL")

        if [[ -z "$DERIVED_SLUG" ]]; then
          echo "Error: Private URLs require an explicit slug."
          echo "Usage: task add-channel -- <slug> \"https://t.me/c/<id>/<post>\""
          exit 1
        fi

        printf "Suggested slug: %s. Press Enter to confirm or type a custom slug: " "$DERIVED_SLUG"
        read -r CUSTOM_SLUG </dev/tty
        if [[ -n "$CUSTOM_SLUG" ]]; then
          SLUG="$CUSTOM_SLUG"
        else
          SLUG="$DERIVED_SLUG"
        fi
      else
        # Two args: slug + URL
        SLUG="$ARG1"
        URL="$ARG2"
        if [[ -z "$URL" ]]; then
          echo "Error: URL is required when providing a slug."
          echo "Usage: task add-channel -- <slug> <url>"
          exit 1
        fi
      fi

      if [[ ! "$SLUG" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "Error: slug must contain only letters, digits, hyphens, and underscores."
        exit 1
      fi
```

**Note:** `read -r CUSTOM_SLUG </dev/tty` is needed because go-task captures stdin. Reading from `/dev/tty` ensures the interactive prompt works.

**Step 3: Verify the change**

Run with a public URL (dry test — will fail at `tdl` but parsing should work):
```bash
task add-channel -- "https://t.me/seeallochnaya/3412"
```
Expected: see prompt `Suggested slug: seeallochnaya. Press Enter to confirm or type a custom slug:`

Run with no args:
```bash
task add-channel
```
Expected: `Error: URL is required.`

Run with private URL only:
```bash
task add-channel -- "https://t.me/c/1234567890/154"
```
Expected: `Error: Private URLs require an explicit slug.`

**Step 4: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: smart slug detection in add-channel command"
```

---

### Task 2: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md` (lines 8-11, 105-120)

**Step 1: Update Quick Start section**

Replace:
```markdown
# Add a new channel (auto-resolves IDs from any Telegram post URL)
task add-channel -- <slug> <url>
```
With:
```markdown
# Add a new channel (auto-resolves IDs and slug from any Telegram post URL)
task add-channel -- <url>
```

**Step 2: Update the task add-channel section**

Replace the `### task add-channel -- \<slug\> \<url\>` heading and examples:

```markdown
### task add-channel -- \<url\>

Creates a new channel directory with config and empty `all-messages.json`. Auto-resolves numeric IDs from any Telegram post URL. For public channels, the slug is derived from the username (with interactive confirmation).

\`\`\`bash
# Public channel — slug auto-derived from username, confirms interactively
task add-channel -- "https://t.me/somechannel/42"

# Public channel with comments (resolves both channel + discussion group IDs)
task add-channel -- "https://t.me/somechannel/42?comment=100"

# Private channel (slug required — no username in URL)
task add-channel -- my-channel "https://t.me/c/1234567890/154"
\`\`\`
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update add-channel usage for smart slug detection"
```

---

### Task 3: Manual end-to-end verification

**Step 1: Run with the original failing command**

```bash
task add-channel -- "https://t.me/seeallochnaya/3412"
```

Expected: prompted for slug confirmation, then channel created (assuming `tdl` is authenticated).

**Step 2: Verify directory created**

```bash
ls downloads/seeallochnaya/
cat downloads/seeallochnaya/channel.json
```

**Step 3: Clean up test channel (if needed)**

```bash
rm -rf downloads/seeallochnaya
```
