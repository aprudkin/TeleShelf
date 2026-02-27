# Thread Media Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-download .mp4 videos from threads during sync for channels with `sync_thread_media` config, plus a backfill command.

**Architecture:** Add thread export + media download logic to `task sync` (gated by `sync_thread_media` in channel.json). Add standalone `task sync-thread-media` for backfilling. Both use the same thread resolution logic: parse entities for discussion group links, fallback to channel-level export.

**Tech Stack:** Bash (Taskfile.yml), Python3 inline scripts, tdl CLI

---

### Task 1: Add thread sync to `task sync`

**Files:**
- Modify: `Taskfile.yml` — sync task, lines 230-377

**Step 1: Add thread sync block after media download (before cleanup)**

Insert after line 348 (`done <<< "$MEDIA_IDS"` / `echo "No media to download."` fi block), before `# Clean up` (line 350):

```bash
      # Sync thread media (if sync_thread_media is configured)
      SYNC_THREAD_EXTS=$(python3 -c "
      import json, sys
      config = json.load(open(sys.argv[1]))
      exts = config.get('sync_thread_media', [])
      print(' '.join(exts))
      " "$CONFIG_FILE")

      if [[ -n "$SYNC_THREAD_EXTS" ]]; then
        DISCUSSION_GROUP_ID=$(python3 -c "
        import json, sys
        print(json.load(open(sys.argv[1])).get('discussion_group_id', ''))
        " "$CONFIG_FILE")

        if [[ -z "$DISCUSSION_GROUP_ID" ]]; then
          echo "Warning: sync_thread_media requires discussion_group_id in channel.json. Skipping thread sync."
        else
          echo ""
          echo "Syncing thread media..."

          # Get new post IDs from temp file
          NEW_POST_IDS=$(python3 -c "
          import json, sys
          with open(sys.argv[1]) as f:
              d = json.load(f)
          for msg in d.get('messages', []):
              print(msg['id'])
          " "$TEMP_FILE")

          for POST_ID in $NEW_POST_IDS; do
            # Find thread ID from post entities
            THREAD_ID=$(python3 -c "
            import json, re, sys
            post_id = int(sys.argv[1])
            discussion_id = sys.argv[2]
            with open(sys.argv[3]) as f:
                d = json.load(f)
            for msg in d.get('messages', []):
                if msg['id'] == post_id:
                    for e in msg.get('entities', []):
                        url = e.get('url', '')
                        m = re.search(r't\.me/c/' + discussion_id + r'/(\d+)', url)
                        if m:
                            print(m.group(1))
                            sys.exit(0)
            print('')
            " "$POST_ID" "$DISCUSSION_GROUP_ID" "$TEMP_FILE")

            THREAD_FILE="$CHANNEL_DIR/threads/thread-${POST_ID}.json"

            if [[ -n "$THREAD_ID" ]]; then
              echo "  Post $POST_ID: exporting thread (thread ID: $THREAD_ID)..."
              tdl chat export -c "$DISCUSSION_GROUP_ID" --all --with-content --reply "$THREAD_ID" -T id -i 1 -i 999999 -o "$THREAD_FILE" 2>&1 || { echo "  Warning: Failed to export thread for post $POST_ID"; continue; }
            else
              echo "  Post $POST_ID: no thread link found, trying channel fallback..."
              tdl chat export -c "$CHANNEL_ID" --all --with-content --reply "$POST_ID" -T id -i 1 -i 999999 -o "$THREAD_FILE" 2>&1 || { echo "  Warning: Failed to export thread for post $POST_ID"; continue; }
            fi

            # Download matching media from thread
            python3 -c "
            import json, os, sys
            thread_file = sys.argv[1]
            exts = sys.argv[2].split()
            discussion_id = sys.argv[3]
            media_dir = sys.argv[4]
            if not os.path.exists(thread_file):
                sys.exit(0)
            with open(thread_file) as f:
                d = json.load(f)
            for msg in d.get('messages', []):
                f_name = msg.get('file', '')
                if not f_name:
                    continue
                if not any(f_name.lower().endswith(ext) for ext in exts):
                    continue
                expected = f'{discussion_id}_{msg[\"id\"]}_{f_name}'
                if os.path.exists(os.path.join(media_dir, expected)):
                    continue
                print(f'{msg[\"id\"]}')
            " "$THREAD_FILE" "$SYNC_THREAD_EXTS" "$DISCUSSION_GROUP_ID" "$CHANNEL_DIR/threads-media/" | while IFS= read -r MSG_ID; do
              echo "    Downloading thread media msg $MSG_ID..."
              tdl dl -u "https://t.me/c/$DISCUSSION_GROUP_ID/$MSG_ID" -d "$CHANNEL_DIR/threads-media/" || echo "    Warning: Failed to download thread media msg $MSG_ID"
            done
          done
        fi
      fi
```

**Step 2: Move `rm -f "$TEMP_FILE"` after the thread sync block**

The thread sync reads from `$TEMP_FILE` to get post entities, so cleanup must come after. Move the `# Clean up` / `rm -f "$TEMP_FILE"` line to after the new thread sync block.

**Step 3: Verify manually**

Run: `task sync -- iishenka-pro`
Expected: If no new posts, exits early (no thread sync triggered). The sync_thread_media block is only reached when there are new posts.

**Step 4: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: add thread media sync to task sync"
```

---

### Task 2: Add `task sync-thread-media` backfill command

**Files:**
- Modify: `Taskfile.yml` — add new task after `sync-all`

**Step 1: Add the sync-thread-media task**

Insert after the `sync-all` task block (after line 426), before `re-export`:

```yaml
  sync-thread-media:
    desc: Download missing thread media for a channel
    summary: |
      Usage: task sync-thread-media -- <slug>

      For each post in a channel, exports threads (if missing) and downloads
      media files matching sync_thread_media extensions. Skips already-downloaded files.

      Requires sync_thread_media in channel.json.

      Example:
        task sync-thread-media -- iishenka-pro
    preconditions:
      - sh: '[ -n "{{.CLI_ARGS}}" ]'
        msg: "Error: slug is required. Usage: task sync-thread-media -- <slug>"
      - sh: '[ -f "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel.json" ]'
        msg: "Error: channel.json not found at {{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel.json"
      - sh: '[ -f "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel-full/all-messages.json" ]'
        msg: "Error: all-messages.json not found"
    silent: true
    cmd: |
      set -eo pipefail

      SLUG="{{.CLI_ARGS}}"
      CHANNEL_DIR="{{.DOWNLOADS_DIR}}/$SLUG"
      CONFIG_FILE="$CHANNEL_DIR/channel.json"
      MESSAGES_FILE="$CHANNEL_DIR/channel-full/all-messages.json"

      # Read config
      CHANNEL_ID=$(python3 -c "import json, sys; print(json.load(open(sys.argv[1]))['channel_id'])" "$CONFIG_FILE")
      DISCUSSION_GROUP_ID=$(python3 -c "import json, sys; print(json.load(open(sys.argv[1])).get('discussion_group_id', ''))" "$CONFIG_FILE")
      SYNC_THREAD_EXTS=$(python3 -c "
      import json, sys
      config = json.load(open(sys.argv[1]))
      exts = config.get('sync_thread_media', [])
      print(' '.join(exts))
      " "$CONFIG_FILE")

      if [[ -z "$SYNC_THREAD_EXTS" ]]; then
        echo "Error: sync_thread_media not configured in channel.json for '$SLUG'."
        exit 1
      fi

      if [[ -z "$DISCUSSION_GROUP_ID" ]]; then
        echo "Error: discussion_group_id required for thread sync."
        exit 1
      fi

      echo "Channel: $SLUG (ID: $CHANNEL_ID, Discussion: $DISCUSSION_GROUP_ID)"
      echo "Media extensions: $SYNC_THREAD_EXTS"
      echo ""

      # Get all post IDs
      POST_IDS=$(python3 -c "
      import json, sys
      with open(sys.argv[1]) as f:
          d = json.load(f)
      for msg in d.get('messages', []):
          print(msg['id'])
      " "$MESSAGES_FILE")

      TOTAL=0
      EXPORTED=0
      DOWNLOADED=0
      SKIPPED=0

      for POST_ID in $POST_IDS; do
        TOTAL=$((TOTAL + 1))
        THREAD_FILE="$CHANNEL_DIR/threads/thread-${POST_ID}.json"

        # Export thread if missing
        if [[ ! -f "$THREAD_FILE" ]]; then
          # Try to find thread ID from post entities
          THREAD_ID=$(python3 -c "
          import json, re, sys
          post_id = int(sys.argv[1])
          discussion_id = sys.argv[2]
          with open(sys.argv[3]) as f:
              d = json.load(f)
          for msg in d.get('messages', []):
              if msg['id'] == post_id:
                  for e in msg.get('entities', []):
                      url = e.get('url', '')
                      m = re.search(r't\.me/c/' + discussion_id + r'/(\d+)', url)
                      if m:
                          print(m.group(1))
                          sys.exit(0)
          print('')
          " "$POST_ID" "$DISCUSSION_GROUP_ID" "$MESSAGES_FILE")

          if [[ -n "$THREAD_ID" ]]; then
            echo "Post $POST_ID: exporting thread (thread ID: $THREAD_ID)..."
            if tdl chat export -c "$DISCUSSION_GROUP_ID" --all --with-content --reply "$THREAD_ID" -T id -i 1 -i 999999 -o "$THREAD_FILE" 2>&1; then
              EXPORTED=$((EXPORTED + 1))
            else
              echo "  Warning: Failed to export thread for post $POST_ID"
              continue
            fi
          else
            echo "Post $POST_ID: no thread link, trying channel fallback..."
            if tdl chat export -c "$CHANNEL_ID" --all --with-content --reply "$POST_ID" -T id -i 1 -i 999999 -o "$THREAD_FILE" 2>&1; then
              EXPORTED=$((EXPORTED + 1))
            else
              echo "  Warning: Failed to export thread for post $POST_ID"
              continue
            fi
          fi
        fi

        # Check thread file exists and find missing media
        if [[ ! -f "$THREAD_FILE" ]]; then
          continue
        fi

        MISSING_IDS=$(python3 -c "
        import json, os, sys
        thread_file = sys.argv[1]
        exts = sys.argv[2].split()
        discussion_id = sys.argv[3]
        media_dir = sys.argv[4]
        with open(thread_file) as f:
            d = json.load(f)
        for msg in d.get('messages', []):
            f_name = msg.get('file', '')
            if not f_name:
                continue
            if not any(f_name.lower().endswith(ext) for ext in exts):
                continue
            expected = f'{discussion_id}_{msg[\"id\"]}_{f_name}'
            if os.path.exists(os.path.join(media_dir, expected)):
                continue
            print(f'{msg[\"id\"]}')
        " "$THREAD_FILE" "$SYNC_THREAD_EXTS" "$DISCUSSION_GROUP_ID" "$CHANNEL_DIR/threads-media/")

        if [[ -z "$MISSING_IDS" ]]; then
          continue
        fi

        while IFS= read -r MSG_ID; do
          echo "  Post $POST_ID: downloading thread media msg $MSG_ID..."
          if tdl dl -u "https://t.me/c/$DISCUSSION_GROUP_ID/$MSG_ID" -d "$CHANNEL_DIR/threads-media/" 2>&1; then
            DOWNLOADED=$((DOWNLOADED + 1))
          else
            echo "  Warning: Failed to download thread media msg $MSG_ID"
            SKIPPED=$((SKIPPED + 1))
          fi
        done <<< "$MISSING_IDS"
      done

      echo ""
      echo "Thread media sync complete for '$SLUG'."
      echo "  Posts processed: $TOTAL"
      echo "  Threads exported: $EXPORTED"
      echo "  Media downloaded: $DOWNLOADED"
      if [[ "$SKIPPED" -gt 0 ]]; then
        echo "  Failed downloads: $SKIPPED"
      fi
```

**Step 2: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: add sync-thread-media backfill command"
```

---

### Task 3: Update channel.json for iishenka-pro

**Files:**
- Modify: `downloads/iishenka-pro/channel.json`

**Step 1: Add sync_thread_media field**

Change from:
```json
{
  "channel_id": "2564209658",
  "discussion_group_id": "2558997551",
  "name": "IIshenka Pro"
}
```

To:
```json
{
  "channel_id": "2564209658",
  "discussion_group_id": "2558997551",
  "name": "IIshenka Pro",
  "sync_thread_media": [".mp4"]
}
```

**Step 2: Commit**

```bash
git add downloads/iishenka-pro/channel.json
git commit -m "feat: enable thread media sync for iishenka-pro"
```

---

### Task 4: Run backfill for iishenka-pro

**Step 1: Run sync-thread-media**

Run: `task sync-thread-media -- iishenka-pro`

Expected: Iterates all 142 posts, exports missing threads, downloads missing .mp4 files. Prints summary at end.

**Step 2: Verify downloaded files**

Run: `ls downloads/iishenka-pro/threads-media/*.mp4 | wc -l`

Expected: More .mp4 files than before (was 14 in threads-media).

**Step 3: No commit** (media files are gitignored)

---

### Task 5: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add sync_thread_media to channel.json format section (around line 50-64)**

Update the example JSON and add field description:

```json
{
  "channel_id": "1234567890",
  "discussion_group_id": "9876543210",
  "name": "My Channel",
  "sync_thread_media": [".mp4"]
}
```

Add to the field list:
- `sync_thread_media` (optional): array of file extensions to auto-download from threads during sync (e.g., `[".mp4"]`). Requires `discussion_group_id`.

**Step 2: Add thread sync mention to `task sync` description (around line 72)**

Add to "What it does" list:
8. If `sync_thread_media` is configured: exports threads for new posts and downloads matching media files into `threads-media/`

**Step 3: Add `task sync-thread-media` section (after `task sync-all`)**

```markdown
### task sync-thread-media -- \<slug\>

Downloads missing thread media for all posts in a channel. Exports thread JSON if not already present, then downloads media files matching `sync_thread_media` extensions.

\`\`\`bash
task sync-thread-media -- iishenka-pro
\`\`\`

What it does:
1. Reads `sync_thread_media` extensions from `channel.json`
2. For each post: checks if `threads/thread-{post_id}.json` exists, exports if missing
3. Finds thread messages with files matching configured extensions
4. Downloads missing files to `threads-media/`
5. Prints summary: posts processed, threads exported, media downloaded
\`\`\`
```

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add sync_thread_media config and sync-thread-media command"
```

---

### Task 6: Verify end-to-end

**Step 1: Run sync with no new posts**

Run: `task sync -- iishenka-pro`
Expected: "No new messages found." — thread sync block is not reached (it only runs for new posts).

**Step 2: Verify thread files exist**

Run: `ls downloads/iishenka-pro/threads/thread-*.json | wc -l`
Expected: More thread files than before the backfill.

**Step 3: Verify media files**

Run: `ls downloads/iishenka-pro/threads-media/*.mp4 | wc -l`
Expected: Increased count from backfill.

**Step 4: Final commit (if any cleanup needed)**

---
