# Multi-Channel Restructure Design

**Date:** 2026-02-19
**Status:** Approved

## Goal

Transform `my-tdl` (single-channel Telegram export) into `scrap-tg` — a multi-channel scraping project with go-task automation.

## Changes

### 1. Rename project

`~/dev/my-tdl` → `~/dev/scrap-tg`

Simple `mv` at filesystem level.

### 2. Restructure downloads/

**Before:**
```
downloads/
  channel-full/          # all-messages.json, texts.md
  channel-main/          # media files
  threads/               # thread JSONs
  threads-media/         # thread media
  channel-threads-media/
  118/                   # standalone exports
  4414/
```

**After:**
```
downloads/
  iishenka-pro/          # channel slug
    channel.yml          # channel config
    channel-full/        # all-messages.json, texts.md
    channel-main/        # media files
    threads/             # thread JSONs
    threads-media/       # thread media
    channel-threads-media/
    118/                 # standalone exports
    4414/
```

Each channel gets its own top-level directory under `downloads/`, named by slug.

### 3. Channel config: channel.yml

Each channel folder contains `channel.yml`:

```yaml
channel_id: "2564209658"
discussion_group_id: "2558997551"  # optional
name: "IIshenka Pro"
```

Parsed in Taskfile via `python3 -c "import yaml; ..."`.

### 4. Taskfile.yml (project-local)

Located at `scrap-tg/Taskfile.yml`.

#### task sync -- \<slug\>

1. Read `channel.yml` from `downloads/<slug>/`
2. Find last message ID from `all-messages.json`
3. Export new messages via `tdl chat export`
4. Merge into `all-messages.json` (new messages prepended, sorted by ID desc)
5. Download media for messages that have files

#### task add-channel -- \<slug\> \<channel-id\> [discussion-group-id]

1. Create directory structure under `downloads/<slug>/`
2. Write `channel.yml`
3. Create empty `all-messages.json` with `{"messages": []}`
4. Create subdirectories: `channel-full/`, `channel-main/`, `threads/`, `threads-media/`

### 5. Delete old scripts

Remove `export-threads.sh` and `reexport-channel-threads.sh` — logic moves to Taskfile.

### 6. Update CLAUDE.md

Rewrite to reflect new multi-channel structure, channel.yml config, and task commands.

## Dependencies

- `tdl` — already installed
- `python3` with `PyYAML` — for parsing channel.yml
- `go-task` — already installed

## Non-goals

- No git init (for now)
- No thread sync automation in Taskfile (manual via tdl for now)
- No texts.md auto-update in sync task (complex formatting, keep manual)
