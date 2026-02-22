# `task sync-all` Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `sync-all` task that syncs all existing channels in one command, with a single reader build at the end.

**Architecture:** Modify existing `sync` task to accept a `SKIP_READER` variable that skips the reader build step. Add a new `sync-all` task that discovers all channels, calls `sync` for each with `SKIP_READER=1`, then builds the reader once at the end.

**Tech Stack:** go-task (Taskfile.yml), zsh

---

### Task 1: Add SKIP_READER support to sync task

**Files:**
- Modify: `Taskfile.yml` (lines 317-321, the reader build block in sync)

**Step 1: Wrap the reader build in a SKIP_READER check**

In `Taskfile.yml`, replace the reader build block at the end of the `sync` task (lines 317-324):

```yaml
      # Build reader
      echo ""
      echo "Building reader..."
      python3 "{{.ROOT_DIR}}/scripts/build_reader.py"

      echo ""
      echo "Sync complete for '$SLUG'."
      echo "  open {{.ROOT_DIR}}/reader/index.html"
```

With:

```yaml
      # Build reader (skip if called from sync-all)
      if [[ -z "${SKIP_READER:-}" ]]; then
        echo ""
        echo "Building reader..."
        python3 "{{.ROOT_DIR}}/scripts/build_reader.py"
        echo ""
        echo "Sync complete for '$SLUG'."
        echo "  open {{.ROOT_DIR}}/reader/index.html"
      else
        echo ""
        echo "Sync complete for '$SLUG'. (reader build skipped)"
      fi
```

**Step 2: Verify sync still works standalone**

Run: `task sync -- iishenka-pro`
Expected: Sync completes as before, reader is built at the end (SKIP_READER is not set).

**Step 3: Verify SKIP_READER works**

Run: `SKIP_READER=1 task sync -- iishenka-pro`
Expected: Sync completes, prints "reader build skipped" instead of building reader.

**Step 4: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: add SKIP_READER support to sync task"
```

---

### Task 2: Add sync-all task

**Files:**
- Modify: `Taskfile.yml` (add new task after `sync`)

**Step 1: Add the sync-all task**

In `Taskfile.yml`, add the following task after the `sync` task (before `build-reader`):

```yaml
  sync-all:
    desc: Sync all channels
    summary: |
      Usage: task sync-all

      Discovers all channel directories in downloads/ and syncs each one.
      Reader is built once at the end. Continues on error.

      Example:
        task sync-all
    silent: true
    cmd: |
      set -o pipefail

      SUCCEEDED=0
      FAILED=0
      FAILED_SLUGS=""

      for CONFIG in "{{.DOWNLOADS_DIR}}"/*/channel.json; do
        [[ -f "$CONFIG" ]] || continue
        SLUG="$(basename "$(dirname "$CONFIG")")"
        echo "========================================="
        echo "Syncing: $SLUG"
        echo "========================================="
        if SKIP_READER=1 task sync -- "$SLUG"; then
          SUCCEEDED=$((SUCCEEDED + 1))
        else
          FAILED=$((FAILED + 1))
          FAILED_SLUGS="$FAILED_SLUGS $SLUG"
        fi
        echo ""
      done

      # Build reader once
      echo "========================================="
      echo "Building reader..."
      echo "========================================="
      python3 "{{.ROOT_DIR}}/scripts/build_reader.py"

      # Summary
      echo ""
      echo "========================================="
      echo "Sync-all complete: $SUCCEEDED succeeded, $FAILED failed."
      if [[ -n "$FAILED_SLUGS" ]]; then
        echo "Failed channels:$FAILED_SLUGS"
      fi
      echo "  open {{.ROOT_DIR}}/reader/index.html"
      echo "========================================="
```

**Step 2: Verify channel discovery**

Run: `task sync-all`
Expected: Both `iishenka-pro` and `vibecoding-tg` are discovered and synced sequentially. Reader is built once at the end. Summary shows counts.

**Step 3: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: add sync-all task to sync all channels"
```

---

### Task 3: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (Task Commands section)

**Step 1: Add sync-all documentation**

In `CLAUDE.md`, after the `task sync` section and before `task add-channel`, add:

```markdown
### task sync-all

Syncs all channels that have a `channel.json` in their `downloads/` directory. Runs `task sync` for each channel sequentially, builds the reader once at the end.

```bash
task sync-all
```

What it does:
1. Discovers all `downloads/*/channel.json` directories
2. Runs `task sync` for each channel (with reader build skipped)
3. On error: logs warning, continues to next channel
4. Builds reader once at the end
5. Prints summary: N succeeded, M failed (with names)
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add sync-all to CLAUDE.md"
```
