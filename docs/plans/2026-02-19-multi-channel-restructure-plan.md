# Multi-Channel Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform `my-tdl` into `scrap-tg` — a multi-channel Telegram scraping project with go-task automation.

**Architecture:** Each channel lives in its own directory under `downloads/<slug>/` with a `channel.yml` config. A single `Taskfile.yml` reads the config and drives all operations via `task sync -- <slug>` and `task add-channel -- <slug> <id> [discussion-id]`.

**Tech Stack:** tdl (Telegram downloader), go-task, python3, PyYAML

**Design doc:** `docs/plans/2026-02-19-multi-channel-restructure-design.md`

**Note:** No git repo — skip all commit steps. No tests — this is a data/scraping project.

---

### Task 1: Install PyYAML dependency

PyYAML is not currently installed but is needed to parse `channel.yml` from Taskfile.

**Step 1: Install PyYAML**

Run: `pip3 install pyyaml`
Expected: Successfully installed PyYAML

**Step 2: Verify**

Run: `python3 -c "import yaml; print(yaml.__version__)"`
Expected: Prints version number (e.g., 6.x)

---

### Task 2: Create channel directory and move data

Move all existing data from flat `downloads/` into `downloads/iishenka-pro/`.

**Files:**
- Move: `downloads/channel-full/` → `downloads/iishenka-pro/channel-full/`
- Move: `downloads/channel-main/` → `downloads/iishenka-pro/channel-main/`
- Move: `downloads/threads/` → `downloads/iishenka-pro/threads/`
- Move: `downloads/threads-media/` → `downloads/iishenka-pro/threads-media/`
- Move: `downloads/channel-threads-media/` → `downloads/iishenka-pro/channel-threads-media/`
- Move: `downloads/118/` → `downloads/iishenka-pro/118/`
- Move: `downloads/4414/` → `downloads/iishenka-pro/4414/`

**Step 1: Create the channel directory**

```bash
mkdir -p downloads/iishenka-pro
```

**Step 2: Move all subdirectories**

```bash
for dir in channel-full channel-main threads threads-media channel-threads-media 118 4414; do
  mv "downloads/$dir" "downloads/iishenka-pro/$dir"
done
```

**Step 3: Verify structure**

Run: `ls downloads/iishenka-pro/`
Expected: `118  4414  channel-full  channel-main  channel-threads-media  threads  threads-media`

Run: `ls downloads/` (should only contain `iishenka-pro/` and `.DS_Store`)

---

### Task 3: Create channel.yml for iishenka-pro

**Files:**
- Create: `downloads/iishenka-pro/channel.yml`

**Step 1: Write channel.yml**

```yaml
channel_id: "2564209658"
discussion_group_id: "2558997551"
name: "IIshenka Pro"
```

**Step 2: Verify parsing**

Run: `python3 -c "import yaml; d=yaml.safe_load(open('downloads/iishenka-pro/channel.yml')); print(d['channel_id'])"`
Expected: `2564209658`

---

### Task 4: Delete old shell scripts

**Files:**
- Delete: `export-threads.sh`
- Delete: `reexport-channel-threads.sh`

**Step 1: Remove scripts**

```bash
rm export-threads.sh reexport-channel-threads.sh
```

**Step 2: Verify**

Run: `ls *.sh`
Expected: No results / "No such file or directory"

---

### Task 5: Create Taskfile.yml with add-channel task

**Files:**
- Create: `Taskfile.yml`

**Step 1: Write Taskfile.yml with add-channel task**

```yaml
version: '3'

vars:
  DOWNLOADS_DIR: "{{.ROOT_DIR}}/downloads"

tasks:
  add-channel:
    desc: "Add a new channel to track"
    summary: |
      Usage: task add-channel -- <slug> <channel-id> [discussion-group-id]

      Creates the directory structure and channel.yml config.

      Examples:
        task add-channel -- my-channel 1234567890
        task add-channel -- my-channel 1234567890 9876543210
    vars:
      ARGS: '{{.CLI_ARGS}}'
    cmds:
      - |
        set -eo pipefail

        # Parse arguments
        args=({{.CLI_ARGS}})
        SLUG="${args[1]}"
        CHANNEL_ID="${args[2]}"
        DISCUSSION_ID="${args[3]:-}"

        if [[ -z "$SLUG" || -z "$CHANNEL_ID" ]]; then
          echo "Usage: task add-channel -- <slug> <channel-id> [discussion-group-id]"
          exit 1
        fi

        CHANNEL_DIR="{{.DOWNLOADS_DIR}}/$SLUG"

        if [[ -d "$CHANNEL_DIR" ]]; then
          echo "Error: Channel directory already exists: $CHANNEL_DIR"
          exit 1
        fi

        echo "Creating channel '$SLUG' (ID: $CHANNEL_ID)..."

        # Create directory structure
        mkdir -p "$CHANNEL_DIR"/{channel-full,channel-main,threads,threads-media}

        # Write channel.yml
        python3 -c "
        import yaml
        config = {
            'channel_id': '$CHANNEL_ID',
            'name': '$SLUG',
        }
        if '$DISCUSSION_ID':
            config['discussion_group_id'] = '$DISCUSSION_ID'
        with open('$CHANNEL_DIR/channel.yml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        "

        # Create empty messages file
        echo '{"messages": []}' > "$CHANNEL_DIR/channel-full/all-messages.json"

        echo "Channel created at: $CHANNEL_DIR"
        echo "Config:"
        cat "$CHANNEL_DIR/channel.yml"
        echo ""
        echo "Next: run 'task sync -- $SLUG' to export messages"
```

**Step 2: Verify add-channel works**

Run: `task add-channel -- test-channel 1111111111 2222222222`
Expected: Creates `downloads/test-channel/` with `channel.yml` and subdirectories

Run: `ls downloads/test-channel/`
Expected: `channel-full  channel-main  channel.yml  threads  threads-media`

Run: `cat downloads/test-channel/channel.yml`
Expected: Shows channel_id, discussion_group_id, name

**Step 3: Clean up test channel**

```bash
rm -rf downloads/test-channel
```

---

### Task 6: Add sync task to Taskfile.yml

**Files:**
- Modify: `Taskfile.yml`

**Step 1: Add sync task**

Add the `sync` task after `add-channel` in the Taskfile:

```yaml
  sync:
    desc: "Sync channel: export new messages + download media"
    summary: |
      Usage: task sync -- <channel-slug>

      Reads channel.yml, exports messages newer than the last saved ID,
      merges them into all-messages.json, and downloads media.

      Example: task sync -- iishenka-pro
    vars:
      SLUG: "{{.CLI_ARGS}}"
      CHANNEL_DIR: "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}"
    preconditions:
      - sh: test -n "{{.CLI_ARGS}}"
        msg: "Usage: task sync -- <channel-slug>"
      - sh: test -f "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel.yml"
        msg: "No channel.yml found in {{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}. Run 'task add-channel' first."
    cmds:
      - |
        set -eo pipefail

        SLUG="{{.CLI_ARGS}}"
        CHANNEL_DIR="{{.CHANNEL_DIR}}"
        MESSAGES_FILE="$CHANNEL_DIR/channel-full/all-messages.json"
        TMP_FILE="/tmp/scrap-tg-new-posts-$SLUG.json"

        # Read config
        CHANNEL_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('$CHANNEL_DIR/channel.yml'))['channel_id'])")

        # Find last exported message ID (0 if empty)
        LAST_ID=$(python3 -c "
        import json
        d = json.load(open('$MESSAGES_FILE'))
        msgs = d.get('messages', [])
        print(max((m['id'] for m in msgs), default=0))
        ")
        NEXT_ID=$((LAST_ID + 1))

        echo "Syncing '$SLUG' (channel $CHANNEL_ID) from message #$NEXT_ID..."

        # Export new messages
        tdl chat export -c "$CHANNEL_ID" --all --with-content \
          -T id -i "$NEXT_ID" -i 999999 \
          -o "$TMP_FILE"

        # Check count
        NEW_COUNT=$(python3 -c "
        import json
        d = json.load(open('$TMP_FILE'))
        print(len(d.get('messages', [])))
        ")

        if [[ "$NEW_COUNT" == "0" ]]; then
          echo "No new messages."
          rm -f "$TMP_FILE"
          exit 0
        fi

        echo "Found $NEW_COUNT new message(s). Merging..."

        # Merge: prepend new messages (sorted desc by ID)
        python3 -c "
        import json

        with open('$MESSAGES_FILE') as f:
            old = json.load(f)
        with open('$TMP_FILE') as f:
            new = json.load(f)

        old['messages'] = new['messages'] + old['messages']

        with open('$MESSAGES_FILE', 'w') as f:
            json.dump(old, f, ensure_ascii=False, indent=2)
        "

        # Download media for messages that have files
        MEDIA_IDS=$(python3 -c "
        import json
        d = json.load(open('$TMP_FILE'))
        for m in d['messages']:
            if m.get('file'):
                print(m['id'])
        ")

        if [[ -n "$MEDIA_IDS" ]]; then
          for MSG_ID in $MEDIA_IDS; do
            echo "Downloading media for #$MSG_ID..."
            tdl dl -u "https://t.me/c/$CHANNEL_ID/$MSG_ID" \
              -d "$CHANNEL_DIR/channel-main/" || echo "  Warning: failed to download #$MSG_ID"
          done
        fi

        rm -f "$TMP_FILE"
        echo "Done! $NEW_COUNT messages synced."
```

**Step 2: Verify sync preconditions work**

Run: `task sync` (no args)
Expected: Error message about usage

Run: `task sync -- nonexistent`
Expected: Error about missing channel.yml

**Step 3: Dry-run sync with real channel**

Run: `task sync -- iishenka-pro`
Expected: Either "No new messages" or exports and merges new messages.

---

### Task 7: Rename project directory

This is the final step since it changes the working directory.

**Files:**
- Rename: `~/dev/my-tdl` → `~/dev/scrap-tg`

**Step 1: Rename**

```bash
mv ~/dev/my-tdl ~/dev/scrap-tg
```

**Step 2: Verify**

Run: `ls ~/dev/scrap-tg/Taskfile.yml`
Expected: File exists

Run: `ls ~/dev/scrap-tg/downloads/iishenka-pro/channel.yml`
Expected: File exists

Run: `task --list` (from ~/dev/scrap-tg/)
Expected: Shows `sync` and `add-channel` tasks

---

### Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Rewrite CLAUDE.md**

Update to reflect:
- New project name (`scrap-tg`)
- Multi-channel support
- `channel.yml` config per channel
- `task sync -- <slug>` and `task add-channel -- <slug> <id> [discussion-id]` commands
- Updated directory structure showing `downloads/<slug>/` pattern
- Remove hardcoded channel IDs from instructions (reference channel.yml instead)
- Keep the "Known Errors and Workarounds" section (still relevant for tdl)
- Update the "How to Save a New Post" section to reference task sync
- Update date

---

## Summary of execution order

1. Install PyYAML
2. Move data into `downloads/iishenka-pro/`
3. Create `channel.yml`
4. Delete old scripts
5. Create Taskfile with `add-channel`
6. Add `sync` task to Taskfile
7. Rename `my-tdl` → `scrap-tg`
8. Update CLAUDE.md
