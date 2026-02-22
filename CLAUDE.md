# TeleShelf — Multi-Channel Telegram Export & Reader

Export and archive Telegram channels using [tdl](https://github.com/iyear/tdl). Supports multiple channels, each in its own directory with a `channel.json` config.

---

## Quick Start

```bash
# Add a new channel (auto-resolves IDs and slug from any Telegram post URL)
task add-channel -- <url>

# Sync new messages + media from a channel
task sync -- <slug>

# Open the reader
open reader/index.html
```

---

## Project Structure

```
TeleShelf/
  Taskfile.yml                # go-task automation (sync, add-channel, build-reader)
  CLAUDE.md                   # Project instructions
  scripts/
    build_reader.py           # Generates combined HTML reader for all channels
  reader/                     # Generated reader output (gitignored)
    index.html                # Self-contained reader with channel switcher
  downloads/
    <channel-slug>/           # One directory per channel
      channel.json            # Channel config (channel_id, discussion_group_id, name)
      tags.json               # Post tags: {"post_id": ["tag1", "tag2"]}
      channel-full/
        all-messages.json     # All channel posts (JSON, sorted by ID desc)
        texts.md              # Human-readable markdown of all posts
      channel-main/           # Downloaded media from posts
                              # Naming: {CHANNEL_ID}_{POST_ID}_{FILE_ID}.{ext}
      threads/                # Thread exports as JSON
                              # Naming: thread-{POST_ID}.json (via discussion group)
                              #         thread-{POST_ID}-channel.json (via channel fallback)
      threads-media/          # Media files from threads
      channel-threads-media/  # Media from channel-level thread exports
```

---

## channel.json Format

Each channel directory contains a `channel.json`:

```json
{
  "channel_id": "1234567890",
  "discussion_group_id": "9876543210",
  "name": "My Channel"
}
```

- `channel_id` (required): Telegram channel numeric ID
- `discussion_group_id` (optional): linked discussion group for comment threads
- `name`: human-readable channel name

---

## Task Commands

### task sync -- \<slug\>

Exports new messages since last saved ID, merges into `all-messages.json`, downloads media for messages with files.

```bash
task sync -- my-channel
```

What it does:
1. Reads `channel.json` to get `channel_id`
2. Finds last message ID from `all-messages.json`
3. Runs `tdl chat export` for messages after that ID
4. Merges new messages into `all-messages.json` (prepended, deduped, sorted desc)
5. Downloads media via `tdl dl` for messages with a `file` field
6. Tags new posts via `claude -p` (haiku model) — auto-assigns 1-4 Russian tags per post into `tags.json`
7. Rebuilds combined HTML reader via `build_reader.py`

**Note:** Does NOT update `texts.md` — that is done manually.
**Note:** Tagging requires Claude Code CLI (`claude`). If unavailable, sync continues without tagging.

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

### task add-channel -- \<url\>

Creates a new channel directory with config and empty `all-messages.json`. Auto-resolves numeric IDs from any Telegram post URL. For public channels, the slug is derived from the username (with interactive confirmation).

```bash
# Public channel — slug auto-derived from username, confirms interactively
task add-channel -- "https://t.me/somechannel/42"

# Public channel with comments (resolves both channel + discussion group IDs)
task add-channel -- "https://t.me/somechannel/42?comment=100"

# Private channel (slug required — no username in URL)
task add-channel -- my-channel "https://t.me/c/1234567890/154"
```

- Slug must be alphanumeric with hyphens/underscores only
- Supports both public (`t.me/<username>/<post>`) and private (`t.me/c/<id>/<post>`) URLs
- Add `?comment=` to auto-detect the discussion group ID via tdl

### task build-reader

Generates the combined reader at `reader/index.html` with all channels. Also called automatically at the end of `task sync`.

```bash
task build-reader
```

---

## How to Save a Thread

### Method 1: Via discussion group (preferred)

Requires the **thread ID in the discussion group**, NOT the channel post ID. Find it from links in the post text (e.g., `?thread=4494`).

```bash
SLUG=my-channel
DISCUSSION_ID=$(python3 -c "import json; print(json.load(open('downloads/$SLUG/channel.json')).get('discussion_group_id', ''))")
tdl chat export -c $DISCUSSION_ID --all --with-content --reply {THREAD_ID} -T id -i 1 -i 999999 -o downloads/$SLUG/threads/thread-{POST_ID}.json
```

### Method 2: Via channel (fallback)

If method 1 returns wrong results, use the channel directly:

```bash
SLUG=my-channel
CHANNEL_ID=$(python3 -c "import json; print(json.load(open('downloads/$SLUG/channel.json'))['channel_id'])")
tdl chat export -c $CHANNEL_ID --all --with-content --reply {POST_ID} -T id -i 1 -i 999999 -o downloads/$SLUG/threads/thread-{POST_ID}-channel.json
```

### Download thread media

```bash
SLUG=my-channel
DISCUSSION_ID=$(python3 -c "import json; print(json.load(open('downloads/$SLUG/channel.json')).get('discussion_group_id', ''))")
tdl dl -u "https://t.me/c/$DISCUSSION_ID/{MSG_ID}" -d downloads/$SLUG/threads-media/
```

---

## Known Errors and Workarounds

### `tdl dl -c` does not exist

`tdl dl` does NOT have a `-c` flag. Always use `tdl dl -u` with a Telegram message URL:
```bash
tdl dl -u "https://t.me/c/1234567890/154" -d downloads/my-channel/channel-main/
```

### Thread export returns wrong messages

`--reply {POST_ID}` in the discussion group uses the **discussion group message ID**, not the channel post ID. Extract the correct thread ID from links in the post text (`?thread=XXXX`) or use channel-level export as fallback.

### Validating thread exports

After export, verify:
- Message timestamps match the post date
- Message content relates to the post topic
- If messages are unrelated, the export hit the wrong thread

---

## Static HTML Reader

A single combined `reader/index.html` serves all channels in a BazQux-style interface.

### Features
- **BazQux-style layout** — sidebar with channel list, compact list view in main area
- **Channel sidebar** — "Latest" (all channels) + per-channel entries with unread counts
- **Compact list view** — one row per post: channel name, title, preview, date
- **Accordion expand** — click a row to expand full post with media, tags, threads
- **Search** — client-side text search in toolbar
- **Light/dark theme** — toggle in toolbar, dark by default
- **Read tracking** — posts marked as read on expand, persisted per-channel in localStorage
- **New post badges** — posts added after last visit highlighted
- **Tag filtering** — sidebar tags + toolbar dropdown
- **Thread display** — inline thread messages in expanded posts
- **Fully offline** — single HTML file, no external dependencies

### Build architecture
- `scripts/build_reader.py` — data loading + Jinja2 rendering
- `scripts/templates/reader.html` — main HTML template
- `scripts/templates/macros.html` — reusable macros (post row, expanded view)
- `scripts/static/reader.css` — BazQux-style CSS
- `scripts/static/reader.js` — reader logic (channel switching, search, tags, read tracking)
- CSS/JS are inlined into the final `reader/index.html` at build time

---

## Tags System

Tags are stored in `tags.json` per channel — a flat JSON object mapping post ID strings to arrays of tag strings.

```json
{
  "42": ["css", "советы"],
  "43": ["javascript", "отладка", "chrome-devtools"]
}
```

- 1-4 tags per post, Russian-language, lowercase
- Reuse existing tags where possible for consistency
- Auto-tagged during `task sync` via Claude Code CLI (haiku model)

---

## Conventions

- **Thread file naming:** `thread-{POST_ID}.json` for discussion group export, `thread-{POST_ID}-channel.json` for channel-level fallback
- **Media file naming:** `{CHANNEL_ID}_{POST_ID}_{FILE_ID}.{ext}` (auto-generated by tdl)
- **Post ordering in all-messages.json:** sorted by ID descending (newest first)
- **Channel slug:** alphanumeric with hyphens and underscores only (`^[a-zA-Z0-9_-]+$`)
- **Tags in tags.json:** 1-4 Russian lowercase tags per post
- **Reader output:** `reader/index.html` — combined reader for all channels

---

## Versioning

Version is tracked via **git tags only** (no version file). Format: `vMAJOR.MINOR.PATCH` (semver).

After completing a bugfix or feature:
1. Remind the user to bump the version
2. If approved: `git tag vX.Y.Z -m "<type>: <description>"`
3. If Homebrew formula needs updating, note that too

---

*Updated: 2026-02-22*
