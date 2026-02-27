# Thread Media Sync Design

**Date:** 2026-02-27
**Status:** Approved

## Problem

`task sync` does not export threads or download thread media. For private channels like iishenka-pro, the author posts Pro-videos in threads, and these need to be downloaded automatically. Additionally, existing posts need a way to backfill missing thread videos.

## Constraints

- tdl does not return sender ID (`FromID = null`) for messages in private channel threads — cannot distinguish author from commenter programmatically.
- Thread export requires the thread ID in the discussion group, not the channel post ID.

## Design

### Configuration

New optional field in `channel.json`:

```json
{
  "channel_id": "2564209658",
  "discussion_group_id": "2558997551",
  "name": "IIshenka Pro",
  "sync_thread_media": [".mp4"]
}
```

`sync_thread_media` — array of file extensions to download from threads. If absent, thread sync is skipped (backward compatible).

### Thread sync during `task sync`

For each new post, when `sync_thread_media` is configured:

1. **Find thread ID** — parse post `entities` for links matching `t.me/c/{discussion_group_id}/{thread_id}`. Fallback: `tdl chat export -c {channel_id} --reply {post_id}`.
2. **Export thread** — `tdl chat export -c {discussion_group_id} --reply {thread_id}` → save to `threads/thread-{post_id}.json`.
3. **Filter messages** — select messages where `file` ends with an extension from `sync_thread_media`.
4. **Download media** — `tdl dl -u "https://t.me/c/{discussion_group_id}/{msg_id}"` → into `threads-media/`.

### New command: `task sync-thread-media`

Backfill command for downloading missing thread videos across all posts:

```bash
task sync-thread-media -- iishenka-pro
```

For each post:

1. Check if `threads/thread-{post_id}.json` exists — if not, export the thread.
2. Find messages with files matching `sync_thread_media` extensions.
3. Check if `{discussion_group_id}_{msg_id}_{filename}` exists in `threads-media/`.
4. If missing — download.

### File locations

- Thread JSON: `threads/thread-{post_id}.json` (existing convention)
- Thread media: `threads-media/` (existing convention)

### Documentation

Update `CLAUDE.md`:

- Add `sync_thread_media` to `channel.json` format description.
- Add `task sync-thread-media` command description.
- Mention automatic thread sync in `task sync` description.
